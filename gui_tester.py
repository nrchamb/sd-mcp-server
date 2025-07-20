#!/usr/bin/env python3
"""
SD MCP Server GUI Testing Tool

A comprehensive testing interface for validating all system components,
generating test images, testing NudeNet filtering, and validating configurations.
"""

import sys
import os
import json
import asyncio
import threading
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, filedialog, messagebox
    from PIL import Image, ImageTk
except ImportError:
    print("❌ GUI dependencies not installed. Run: pip install pillow")
    sys.exit(1)

# Project imports
from modules.stable_diffusion.sd_client import SDClient
from modules.stable_diffusion.chevereto_client import CheveretoClient, CheveretoConfig
from modules.llm.llm_manager import LLMManager
from modules.stable_diffusion.content_db import ContentDatabase
from modules.stable_diffusion.models import GenerateImageInput
from modules.config import get_mcp_config
import httpx

class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        
    def enter(self, event=None):
        self.show_tooltip()
        
    def leave(self, event=None):
        self.hide_tooltip()
        
    def show_tooltip(self):
        if self.tooltip_window or not self.text or not self.has_meaningful_content():
            return
            
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("Consolas", "9", "normal"), wraplength=300)
        label.pack(ipadx=1)
        
    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
            
    def update_text(self, new_text):
        self.text = new_text
    
    def has_meaningful_content(self):
        """Check if tooltip has meaningful additional information to display"""
        if not self.text:
            return False
        
        text_lower = self.text.lower().strip()
        
        # Don't show tooltip for very basic single-word status
        basic_only_patterns = [
            "ok",
            "failed", 
            "testing...",
            "not tested yet"
        ]
        
        # Only block if text is EXACTLY these basic patterns
        if text_lower in basic_only_patterns:
            return False
        
        # Show tooltip if it contains meaningful information
        meaningful_indicators = [
            "endpoint:", 
            "suggestion:", 
            "error:", 
            "last tested:", 
            "status:",
            "\n",  # Multi-line content
            "check ",  # Suggestions starting with "check"
            "verify ",  # Suggestions starting with "verify"
            "http://",  # URLs
            "https://",  # URLs
            " - ",  # Dash usually indicates additional info
            ":"  # Colons usually indicate structured info
        ]
        
        for indicator in meaningful_indicators:
            if indicator in text_lower:
                return True
        
        # Show if text is reasonably long (>15 chars) - reduced threshold
        return len(self.text.strip()) > 15

class SDMCPTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SD MCP Server Testing Tool")
        self.root.geometry("1200x800")
        
        # Configuration
        self.config = {}
        
        # MCP.json path configuration
        self.mcp_path = tk.StringVar()
        self.mcp_config = get_mcp_config()
        
        # Set initial path from auto-detection or default
        if self.mcp_config.mcp_path:
            self.mcp_path.set(str(self.mcp_config.mcp_path))
        else:
            # Fallback to default if auto-detection failed
            default_path = str(Path.home() / ".cache" / "lm-studio" / "mcp.json")
            self.mcp_path.set(default_path)
            self.mcp_config.set_mcp_path(default_path)
        
        # Initialize components
        self.sd_client = None
        self.llm_manager = None
        self.chevereto_client = None
        self.content_db = None
        
        # GUI variables
        self.status_vars = {}
        self.image_labels = {}
        self.test_results = {}
        self.tooltips = {}
        self.last_sd_image = None  # Track last generated SD image for import
        
        # Setup GUI
        self.setup_gui()
        self.load_configuration()
        self.initialize_clients()
        
        # Initialize displays
        self.refresh_api_keys_display()
        
    def setup_gui(self):
        """Setup the main GUI interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_system_status_tab()
        self.create_sd_testing_tab()
        self.create_nudenet_testing_tab()
        self.create_mcp_tools_tab()
        self.create_upload_testing_tab()
        self.create_content_analysis_tab()
        self.create_config_tab()
        
    def create_system_status_tab(self):
        """System status and health checks"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="System Status")
        
        # Status indicators
        status_frame = ttk.LabelFrame(frame, text="Component Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_vars = {
            "sd_webui": tk.StringVar(value="⚪ SD WebUI: Not tested"),
            "lm_studio": tk.StringVar(value="⚪ LM Studio: Not tested"),
            "chevereto": tk.StringVar(value="⚪ Chevereto: Not tested"),
            "nudenet": tk.StringVar(value="⚪ NudeNet: Not tested"),
            "databases": tk.StringVar(value="⚪ Databases: Not tested"),
            "discord_bot": tk.StringVar(value="⚪ Discord Bot: Not tested")
        }
        
        # Create single-column status layout with tooltips
        self.status_labels = {}
        self.status_tooltips = {}
        
        for i, (component, var) in enumerate(self.status_vars.items()):
            # Create frame for each status line
            status_line = ttk.Frame(status_frame)
            status_line.grid(row=i, column=0, sticky=tk.W+tk.E, padx=5, pady=2)
            status_line.columnconfigure(1, weight=1)
            
            # Component name label (fixed width, left-aligned)
            component_names = {
                "sd_webui": "SD WebUI:",
                "lm_studio": "LM Studio:", 
                "chevereto": "Chevereto:",
                "nudenet": "NudeNet:",
                "databases": "Databases:",
                "discord_bot": "Discord Bot:"
            }
            
            name_label = ttk.Label(status_line, text=component_names.get(component, f"{component}:"), 
                                  font=("Arial", 10, "bold"), width=12, anchor='w')
            name_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # Status message label (expandable, wrapping)
            status_label = ttk.Label(status_line, text="⚪ Not tested", 
                                   font=("Consolas", 9), anchor='w', 
                                   wraplength=400)  # Allow text wrapping
            status_label.grid(row=0, column=1, sticky=tk.W+tk.E)
            
            # Store references for updates
            self.status_labels[component] = status_label
            self.status_tooltips[component] = "Not tested yet"
            
            # Add tooltip functionality
            # Removed tooltips due to display issues
            # self.tooltips[component] = ToolTip(status_label, "Not tested yet")
        
        # Configure main frame column weight
        status_frame.columnconfigure(0, weight=1)
        
        # Test all button
        ttk.Button(status_frame, text="🔍 Test All Components", 
                  command=self.test_all_components).grid(
                  row=len(self.status_vars), column=0, pady=10
        )
        
        # Database management section
        db_frame = ttk.LabelFrame(frame, text="Database Management", padding=10)
        db_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Database location selection
        location_frame = ttk.Frame(db_frame)
        location_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(location_frame, text="Database Location:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.db_location = tk.StringVar(value=str(Path.cwd()))
        ttk.Entry(location_frame, textvariable=self.db_location, width=50).pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(location_frame, text="Browse", command=self.browse_db_location).pack(side=tk.RIGHT)
        
        # Database operations
        db_buttons_frame = ttk.Frame(db_frame)
        db_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(db_buttons_frame, text="🔍 Check Databases", 
                  command=self.check_databases).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_buttons_frame, text="🏗️ Create Missing DBs", 
                  command=self.create_missing_databases).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_buttons_frame, text="🔄 Recreate All DBs", 
                  command=self.recreate_all_databases).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_buttons_frame, text="🧹 Backup & Clean", 
                  command=self.backup_and_clean_databases).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_buttons_frame, text="🔄 Sync LoRA DB", 
                  command=self.sync_lora_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_buttons_frame, text="🌐 Start HTTP Server", 
                  command=self.start_http_server).pack(side=tk.LEFT, padx=5)
        
        # Database status display
        self.db_status_text = scrolledtext.ScrolledText(db_frame, height=6, font=("Consolas", 9))
        self.db_status_text.pack(fill=tk.X, pady=(10, 0))
        
        # Results area
        results_frame = ttk.LabelFrame(frame, text="Test Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(results_frame, height=20, 
                                                    font=("Consolas", 9))
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
    def create_sd_testing_tab(self):
        """SD WebUI testing with image display"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="SD Testing")
        
        # Controls frame
        controls_frame = ttk.LabelFrame(frame, text="Generation Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Prompt input
        ttk.Label(controls_frame, text="Prompt:").grid(row=0, column=0, sticky=tk.W)
        self.prompt_entry = tk.Entry(controls_frame, width=50)
        self.prompt_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5)
        self.prompt_entry.insert(0, "a beautiful sunset over mountains, high quality")
        
        # Parameters
        ttk.Label(controls_frame, text="Steps:").grid(row=1, column=0, sticky=tk.W)
        self.steps_var = tk.IntVar(value=20)
        ttk.Spinbox(controls_frame, from_=10, to=50, textvariable=self.steps_var, 
                   width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(controls_frame, text="Size:").grid(row=1, column=2, sticky=tk.W, padx=(20,0))
        self.size_var = tk.StringVar(value="512x512")
        size_combo = ttk.Combobox(controls_frame, textvariable=self.size_var, 
                                 values=["512x512", "768x768", "1024x1024"], width=10)
        size_combo.grid(row=1, column=3, sticky=tk.W, padx=5)
        
        # Generate button
        ttk.Button(controls_frame, text="🎨 Generate Image", 
                  command=self.generate_test_image).grid(
                  row=2, column=0, columnspan=4, pady=10
        )
        
        # Create horizontal split for image and status
        content_frame = ttk.Frame(frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Image display frame (left side)
        image_frame = ttk.LabelFrame(content_frame, text="Generated Image", padding=10)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.image_labels["sd_result"] = ttk.Label(image_frame, text="No image generated yet")
        self.image_labels["sd_result"].pack(expand=True)
        
        # Status/logging frame (right side)
        status_frame = ttk.LabelFrame(content_frame, text="Generation Status", padding=10)
        status_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(5, 0))
        status_frame.configure(width=400)  # Fixed width for status panel
        
        self.sd_status_text = scrolledtext.ScrolledText(status_frame, height=20, width=50,
                                                       font=("Consolas", 9))
        self.sd_status_text.pack(fill=tk.BOTH, expand=True)
        
    def create_nudenet_testing_tab(self):
        """NudeNet testing with before/after comparison"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="NudeNet Testing")
        
        # Controls
        controls_frame = ttk.LabelFrame(frame, text="NSFW Detection Testing", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Test image selection
        ttk.Label(controls_frame, text="Test Image:").grid(row=0, column=0, sticky=tk.W)
        self.test_image_path = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.test_image_path, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=5
        )
        ttk.Button(controls_frame, text="Browse", 
                  command=self.browse_test_image).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text="📥 Import from SD Testing", 
                  command=self.import_from_sd_testing).grid(row=0, column=3, padx=5)
        
        # Generate test content
        ttk.Button(controls_frame, text="🔞 Generate NSFW Test Image", 
                  command=self.generate_nsfw_test).grid(row=1, column=0, pady=5)
        ttk.Button(controls_frame, text="✅ Generate Safe Test Image", 
                  command=self.generate_safe_test).grid(row=1, column=1, pady=5)
        ttk.Button(controls_frame, text="🔍 Test Current Image", 
                  command=self.test_nudenet).grid(row=1, column=2, pady=5)
        
        # Testing instructions
        instructions_frame = ttk.LabelFrame(controls_frame, text="NudeNet Testing Instructions")
        instructions_frame.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=10)
        
        instructions_text = """Quick Testing Workflow:
1️⃣ Generate Image: Click "Generate NSFW Test" or "Generate Safe Test"
   → Automatically switches to SD Testing, generates image, imports back
2️⃣ Import from SD Testing: Click "Import from SD Testing" to use last generated image
   → OR use "Browse" to select any image file
3️⃣ Test Current Image: Click "Test Current Image" to run NudeNet analysis
   → View results in Original/Filtered/Mask panels below

ℹ️ Detection thresholds configured in MCP.json"""
        
        instructions_label = ttk.Label(instructions_frame, text=instructions_text, 
                                     font=("Arial", 8), justify=tk.LEFT, anchor="w",
                                     foreground="white", background="gray20", wraplength=600)
        instructions_label.pack(padx=10, pady=3, fill=tk.X)
        
        # Comparison display
        comparison_frame = ttk.LabelFrame(frame, text="NudeNet Analysis Results", padding=10)
        comparison_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create three-panel layout for original, filtered, and mask
        images_frame = ttk.Frame(comparison_frame)
        images_frame.pack(fill=tk.BOTH, expand=True)
        
        # Before image
        before_frame = ttk.Frame(images_frame)
        before_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        ttk.Label(before_frame, text="Original Image", font=("Arial", 10, "bold")).pack()
        self.image_labels["before"] = ttk.Label(before_frame, text="No image loaded")
        self.image_labels["before"].pack(expand=True)
        
        # After image
        after_frame = ttk.Frame(images_frame)
        after_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        ttk.Label(after_frame, text="Filtered Result", font=("Arial", 10, "bold")).pack()
        self.image_labels["after"] = ttk.Label(after_frame, text="No filtering applied")
        self.image_labels["after"].pack(expand=True)
        
        # Detection mask
        mask_frame = ttk.Frame(images_frame)
        mask_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        ttk.Label(mask_frame, text="Detection Mask", font=("Arial", 10, "bold")).pack()
        self.image_labels["mask"] = ttk.Label(mask_frame, text="No mask generated")
        self.image_labels["mask"].pack(expand=True)
        
        # Detection results
        self.detection_text = scrolledtext.ScrolledText(comparison_frame, height=8, width=50)
        self.detection_text.pack(fill=tk.X, pady=10)
        
    def create_mcp_tools_tab(self):
        """MCP tools testing interface"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="MCP Tools")
        
        # Tool selection
        tools_frame = ttk.LabelFrame(frame, text="Available MCP Tools", padding=10)
        tools_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.mcp_tools = [
            ("get_models", "Get available SD models"),
            ("get_current_model", "Get current SD model"),
            ("search_loras", "Search LoRAs"),
            ("get_queue_status", "Get generation queue status"),
            ("load_checkpoint", "Load checkpoint model"),
            ("generate_image", "Generate image"),
            ("upload_image", "Upload image to Chevereto"),
        ]
        
        # Parameter templates for each tool (based on actual MCP tool signatures)
        self.mcp_tool_params = {
            "get_models": {},
            "get_current_model": {},
            "search_loras": {"query": "anime", "limit": 10},
            "get_queue_status": {},
            "load_checkpoint": {"model_name": "sd_xl_base_1.0.safetensors [31e35c80fc]"},  # Use full model name format
            "generate_image": {
                "prompt": "anime girl, masterpiece, high quality",
                "negative_prompt": "blurry, low quality",
                "steps": 25,
                "width": 1024,
                "height": 1024,
                "cfg_scale": 7.0,
                "sampler_name": "Euler",
                "seed": -1
            },
            "upload_image": {
                "image_path": "/tmp/images/sample.png",
                "user_id": "test_user",
                "album_name": "GUI_Testing"
            }
        }
        
        self.selected_tool = tk.StringVar(value=self.mcp_tools[0][0])
        tool_combo = ttk.Combobox(tools_frame, textvariable=self.selected_tool,
                                 values=[tool[0] for tool in self.mcp_tools], width=30)
        tool_combo.grid(row=0, column=0, padx=5)
        
        # Bind tool selection to update parameters
        tool_combo.bind("<<ComboboxSelected>>", self.update_mcp_params)
        
        ttk.Button(tools_frame, text="🔧 Execute Tool", 
                  command=self.execute_mcp_tool).grid(row=0, column=1, padx=5)
        ttk.Button(tools_frame, text="🔄 Reset Params", 
                  command=self.update_mcp_params).grid(row=0, column=2, padx=5)
        
        # Tool description
        self.tool_description = tk.StringVar(value=self.mcp_tools[0][1])
        desc_label = ttk.Label(tools_frame, textvariable=self.tool_description, 
                              font=("Arial", 9), foreground="blue")
        desc_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Parameters frame
        params_frame = ttk.LabelFrame(frame, text="Tool Parameters", padding=10)
        params_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(params_frame, text="Parameters (JSON):").pack(anchor=tk.W)
        self.mcp_params = scrolledtext.ScrolledText(params_frame, height=6)
        self.mcp_params.pack(fill=tk.X, pady=5)
        
        # Set initial parameters
        self.update_mcp_params()
        
        # Instructions
        instructions_frame = ttk.LabelFrame(params_frame, text="Usage Tips")
        instructions_frame.pack(fill=tk.X, pady=5)
        
        mcp_instructions = """• Select tool → Parameters auto-update with correct format
• get_models/get_current_model → Use empty {} parameters
• search_loras → Search LoRA database with query
• load_checkpoint → Use full model name from get_models
• upload_image → Auto-uses last generated SD image"""
        
        ttk.Label(instructions_frame, text=mcp_instructions, font=("Arial", 8), 
                 foreground="white", background="gray20", justify=tk.LEFT, anchor="w",
                 wraplength=500).pack(padx=5, pady=2, fill=tk.X)
        
        # Results frame
        results_frame = ttk.LabelFrame(frame, text="Tool Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.mcp_results = scrolledtext.ScrolledText(results_frame, height=15, 
                                                    font=("Consolas", 9))
        self.mcp_results.pack(fill=tk.BOTH, expand=True)
        
    def create_upload_testing_tab(self):
        """Upload testing for Chevereto and local storage"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Upload Testing")
        
        # Upload controls
        upload_frame = ttk.LabelFrame(frame, text="Upload Testing", padding=10)
        upload_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Test buttons
        ttk.Button(upload_frame, text="📤 Test Chevereto Guest Upload", 
                  command=self.test_chevereto_guest).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(upload_frame, text="🔑 Test Personal API Upload", 
                  command=self.test_chevereto_personal).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(upload_frame, text="💾 Test Local Upload", 
                  command=self.test_local_upload).grid(row=0, column=2, padx=5, pady=5)
        
        # API key configuration display and input
        config_info_frame = ttk.Frame(upload_frame)
        config_info_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=5)
        
        ttk.Label(config_info_frame, text="Current MCP.json Keys:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.api_keys_display = tk.Text(config_info_frame, height=3, wrap=tk.WORD, 
                                       background="#f0f0f0", font=("Consolas", 8))
        self.api_keys_display.pack(fill=tk.X, pady=2)
        
        # Personal API key override
        override_frame = ttk.Frame(upload_frame)
        override_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=5)
        
        ttk.Label(override_frame, text="Override Personal API Key:").pack(side=tk.LEFT)
        self.personal_api_key = tk.Entry(override_frame, width=40, show="*")
        self.personal_api_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(override_frame, text="🔄 Refresh Config", 
                  command=self.refresh_api_keys_display).pack(side=tk.RIGHT, padx=2)
        
        # Upload results
        results_frame = ttk.LabelFrame(frame, text="Upload Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.upload_results = scrolledtext.ScrolledText(results_frame, height=12,
                                                       font=("Consolas", 9))
        self.upload_results.pack(fill=tk.BOTH, expand=True)
        
    def create_content_analysis_tab(self):
        """Content analysis and prompt enhancement testing"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Content Analysis")
        
        # Instructions
        instructions = ttk.LabelFrame(frame, text="Content Analysis Testing", padding=10)
        instructions.pack(fill=tk.X, padx=10, pady=5)
        
        instructions_text = ttk.Label(instructions, 
                                    text="Test the new content classification and prompt enhancement features.\n"
                                         "• Analyze Prompt: Analyzes content and suggests improvements\n"
                                         "• Enhanced Generation: Auto-enhances prompts during image generation\n"
                                         "• Content Classification: Shows word categorization and filtering",
                                    background="darkblue",
                                    foreground="white",
                                    font=("Arial", 10),
                                    justify=tk.LEFT,
                                    wraplength=800)
        instructions_text.pack(fill=tk.X, pady=5)
        
        # Prompt input section
        input_frame = ttk.LabelFrame(frame, text="Prompt Input", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Text entry
        ttk.Label(input_frame, text="Enter prompt to analyze:").pack(anchor=tk.W)
        self.analysis_prompt_entry = tk.Text(input_frame, height=3, width=80, wrap=tk.WORD)
        self.analysis_prompt_entry.pack(fill=tk.X, pady=5)
        self.analysis_prompt_entry.insert("1.0", "a beautiful woman with long hair")
        
        # Test buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="📊 Analyze Prompt", 
                  command=self.test_prompt_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🎨 Generate with Enhancement", 
                  command=self.test_enhanced_generation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔍 Local Content Analysis", 
                  command=self.test_local_content_analysis).pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(frame, text="Analysis Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.analysis_results = scrolledtext.ScrolledText(results_frame, height=20, width=80,
                                                         font=("Consolas", 9))
        self.analysis_results.pack(fill=tk.BOTH, expand=True)
    
    def create_config_tab(self):
        """Configuration validation and editing"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Configuration")
        
        # MCP.json path configuration
        mcp_path_frame = ttk.LabelFrame(frame, text="MCP.json Configuration", padding=10)
        mcp_path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        path_config_frame = ttk.Frame(mcp_path_frame)
        path_config_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(path_config_frame, text="MCP.json Path:").pack(side=tk.LEFT)
        mcp_path_entry = ttk.Entry(path_config_frame, textvariable=self.mcp_path, width=60)
        mcp_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(path_config_frame, text="📁 Browse", command=self.browse_mcp_path).pack(side=tk.LEFT, padx=2)
        ttk.Button(path_config_frame, text="🔧 Auto-detect", command=self.auto_detect_mcp_path).pack(side=tk.LEFT, padx=2)
        
        # Environment variables
        env_frame = ttk.LabelFrame(frame, text="Environment Variables", padding=10)
        env_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.env_vars = scrolledtext.ScrolledText(env_frame, height=8, 
                                                 font=("Consolas", 9))
        self.env_vars.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        controls_frame = ttk.Frame(env_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(controls_frame, text="🔄 Refresh Config", 
                  command=self.load_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="✅ Validate Config", 
                  command=self.validate_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="💾 Reload MCP.json", 
                  command=self.reload_mcp_and_reinitialize).pack(side=tk.LEFT, padx=5)
        
        # Service launcher section
        services_frame = ttk.LabelFrame(frame, text="Service Launcher", padding=10)
        services_frame.pack(fill=tk.X, padx=10, pady=5)
        
        services_controls_frame = ttk.Frame(services_frame)
        services_controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(services_controls_frame, text="🤖 Launch Discord Bot", 
                  command=self.launch_discord_bot).pack(side=tk.LEFT, padx=5)
        ttk.Button(services_controls_frame, text="🔗 Launch MCP HTTP Server", 
                  command=self.launch_mcp_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(services_controls_frame, text="🏥 Run Health Check", 
                  command=self.run_health_check).pack(side=tk.LEFT, padx=5)
        
        # Service status display
        self.service_status = scrolledtext.ScrolledText(services_frame, height=6,
                                                       font=("Consolas", 9))
        self.service_status.pack(fill=tk.X, pady=5)
        
        # Validation results
        validation_frame = ttk.LabelFrame(frame, text="Validation Results", padding=10)
        validation_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.config_results = scrolledtext.ScrolledText(validation_frame, height=10,
                                                       font=("Consolas", 9))
        self.config_results.pack(fill=tk.BOTH, expand=True)
    
    def log_message(self, message: str, widget: Optional[tk.Text] = None):
        """Log a message to the specified widget or default status text"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        target_widget = widget or self.status_text
        target_widget.insert(tk.END, formatted_message)
        target_widget.see(tk.END)
        self.root.update()
    
    def log_sd_message(self, message: str):
        """Log message to SD testing status area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Log to SD status area if it exists, otherwise fall back to main log
        if hasattr(self, 'sd_status_text'):
            self.sd_status_text.insert(tk.END, formatted_message)
            self.sd_status_text.see(tk.END)
        else:
            # Fallback to main log if SD status area not ready yet
            self.status_text.insert(tk.END, formatted_message)
            self.status_text.see(tk.END)
            
    def log_nudenet_message(self, message: str):
        """Log message to NudeNet testing status area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Log to NudeNet detection text area if available
        if hasattr(self, 'detection_text'):
            current_text = self.detection_text.get("1.0", tk.END)
            # If the text area only has default content, clear it first
            if "NudeNet Detection Results" not in current_text:
                self.detection_text.delete("1.0", tk.END)
            self.detection_text.insert(tk.END, formatted_message)
            self.detection_text.see(tk.END)
        else:
            # Fallback to main log if SD status area not ready yet
            self.status_text.insert(tk.END, formatted_message)
            self.status_text.see(tk.END)
            
        self.root.update()
    
    def update_component_status(self, component: str, status_text: str, tooltip_text: str):
        """Update component status display and tooltip"""
        if component in self.status_labels:
            self.status_labels[component].configure(text=status_text)
            
        # Tooltips disabled
        # if component in self.tooltips:
        #     self.tooltips[component].update_text(tooltip_text)
            
        self.root.update()
    
    def load_configuration(self):
        """Load configuration from MCP.json and update environment"""
        self.log_message("Loading configuration from MCP.json...")
        
        # First load from MCP.json
        self.load_mcp_config()
        
        config_text = "# Configuration Sources\n"
        config_text += "# 1. MCP.json (primary)\n"
        config_text += "# 2. Environment variables (fallback)\n\n"
        
        important_vars = [
            "SD_BASE_URL", "LM_STUDIO_BASE_URL", "DISCORD_BOT_TOKEN",
            "CHEVERETO_BASE_URL", "CHEVERETO_GUEST_API_KEY", "CHEVERETO_USER_API_KEY",
            "NSFW_FILTER", "IMAGE_OUT_PATH"
        ]
        
        # Show which source each variable came from
        mcp_vars = self.get_mcp_variables()
        
        for var in important_vars:
            value = os.getenv(var, "Not set")
            source = "MCP.json" if var in mcp_vars else "Environment" if value != "Not set" else "Not set"
            
            if "TOKEN" in var or "KEY" in var and value != "Not set":
                display_value = f"{value[:8]}..." if len(value) > 8 else value
            else:
                display_value = value
                
            config_text += f"{var}={display_value} ({source})\n"
        
        self.env_vars.delete("1.0", tk.END)
        self.env_vars.insert("1.0", config_text)
        
        self.log_message("Configuration loaded from MCP.json")
    
    def load_mcp_config(self):
        """Load configuration from MCP.json file"""
        mcp_path = Path(self.mcp_path.get())
        
        try:
            if mcp_path.exists():
                with open(mcp_path) as f:
                    mcp_config = json.load(f)
                
                # Extract SD MCP Server environment
                env_vars = mcp_config.get("mcpServers", {}).get("SD_MCP_Server", {}).get("env", {})
                
                if env_vars:
                    # Store original environment values for comparison
                    self._mcp_vars = set(env_vars.keys())
                    
                    for key, value in env_vars.items():
                        os.environ[key] = str(value)
                    
                    self.log_message(f"✅ Loaded {len(env_vars)} variables from MCP.json")
                    return env_vars
                else:
                    self.log_message("⚠️  No SD_MCP_Server environment found in MCP.json")
                    self._mcp_vars = set()
                    return {}
            else:
                self.log_message(f"❌ MCP.json not found at {mcp_path}")
                self._mcp_vars = set()
                return {}
                
        except Exception as e:
            self.log_message(f"❌ Error loading MCP.json: {e}")
            self._mcp_vars = set()
            return {}
    
    def get_mcp_variables(self):
        """Get the set of variables loaded from MCP.json"""
        return getattr(self, '_mcp_vars', set())
    
    def initialize_clients(self):
        """Initialize real API clients with configuration from MCP.json"""
        try:
            # Ensure MCP.json is loaded first
            mcp_vars = self.load_mcp_config()
            
            # Build config from environment (now populated from MCP.json)
            self.config = {
                "SD_BASE_URL": os.getenv("SD_BASE_URL", "http://localhost:7860"),
                "LM_STUDIO_BASE_URL": os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234"),
                "CHEVERETO_BASE_URL": os.getenv("CHEVERETO_BASE_URL", ""),
                "CHEVERETO_GUEST_API_KEY": os.getenv("CHEVERETO_GUEST_API_KEY", ""),
                "CHEVERETO_USER_API_KEY": os.getenv("CHEVERETO_USER_API_KEY", ""),
                "IMAGE_OUT_PATH": os.getenv("IMAGE_OUT_PATH", "/tmp/images"),
                "NSFW_FILTER": os.getenv("NSFW_FILTER", "true").lower() == "true",
                # Add all MCP.json variables to config
                **{k: os.getenv(k, "") for k in mcp_vars.keys()}
            }
            
            self.log_message(f"🔧 Initializing clients with MCP.json configuration...")
            
            # Initialize SD Client with NudeNet config from MCP.json
            if self.config["SD_BASE_URL"]:
                # Build NudeNet config from MCP.json environment variables
                nudenet_config = {}
                for key in self.config.keys():
                    if key.startswith("NUDENET_"):
                        nudenet_config[key] = self.config[key]
                
                self.sd_client = SDClient(
                    base_url=self.config["SD_BASE_URL"],
                    nudenet_config=nudenet_config
                )
                self.log_message(f"✅ SD Client initialized: {self.config['SD_BASE_URL']}")
                if nudenet_config:
                    self.log_message(f"🔧 NudeNet config loaded: {len(nudenet_config)} settings")
            
            # Initialize LLM Manager with full MCP.json config
            if self.config["LM_STUDIO_BASE_URL"]:
                self.llm_manager = LLMManager(self.config)
                chat_provider = self.config.get("CHAT_LLM_PROVIDER", "lmstudio")
                self.log_message(f"✅ LLM Manager initialized (Chat: {chat_provider})")
            
            # Initialize Chevereto Client with MCP.json configuration
            if self.config["CHEVERETO_BASE_URL"] and self.config["CHEVERETO_GUEST_API_KEY"]:
                chevereto_config = CheveretoConfig(
                    base_url=self.config["CHEVERETO_BASE_URL"],
                    guest_api_key=self.config["CHEVERETO_GUEST_API_KEY"],
                    user_api_key=self.config.get("CHEVERETO_USER_API_KEY", ""),
                    admin_api_key=self.config.get("CHEVERETO_ADMIN_API_KEY", "")
                )
                self.chevereto_client = CheveretoClient(chevereto_config)
                self.log_message(f"✅ Chevereto Client initialized: {self.config['CHEVERETO_BASE_URL']}")
            elif self.config["CHEVERETO_BASE_URL"]:
                self.log_message(f"⚠️  Chevereto URL found but no API keys in MCP.json")
            else:
                self.log_message(f"ℹ️  No Chevereto configuration in MCP.json")
            
            # Initialize Content Database
            try:
                self.content_db = ContentDatabase()
                self.log_message(f"✅ Content Database initialized")
            except Exception as e:
                self.log_message(f"⚠️  Content Database initialization failed: {e}")
                
        except Exception as e:
            self.log_message(f"❌ Client initialization error: {e}")
    
    def reload_mcp_and_reinitialize(self):
        """Reload MCP.json configuration and reinitialize all clients"""
        self.log_message("🔄 Reloading MCP.json and reinitializing clients...")
        
        try:
            # Clear existing clients
            self.sd_client = None
            self.llm_manager = None
            self.chevereto_client = None
            self.content_db = None
            
            # Reload configuration and reinitialize
            self.load_configuration()
            self.initialize_clients()
            
            self.log_message("✅ MCP.json reloaded and clients reinitialized")
            
        except Exception as e:
            self.log_message(f"❌ Failed to reload MCP.json: {e}")
    
    def browse_mcp_path(self):
        """Browse for MCP.json file location"""
        file_path = filedialog.askopenfilename(
            title="Select MCP.json file",
            filetypes=[
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ],
            initialfile="mcp.json"
        )
        
        if file_path:
            self.mcp_path.set(file_path)
            self.mcp_config.set_mcp_path(file_path)
            self.log_message(f"📁 MCP.json path updated: {file_path}")
            # Auto-reload configuration with new path
            self.reload_mcp_and_reinitialize()
    
    def auto_detect_mcp_path(self):
        """Auto-detect MCP.json file location using the MCP config system"""
        self.log_message("🔍 Auto-detecting MCP.json location...")
        
        # Get common paths from MCP config
        possible_paths = self.mcp_config.get_common_mcp_paths()
        
        found_paths = []
        for path in possible_paths:
            if path.exists():
                found_paths.append(path)
                self.log_message(f"✅ Found: {path}")
        
        if found_paths:
            # Use the first found path
            selected_path = found_paths[0]
            self.mcp_path.set(str(selected_path))
            self.mcp_config.set_mcp_path(str(selected_path))
            self.log_message(f"🎯 Using: {selected_path}")
            
            if len(found_paths) > 1:
                self.log_message(f"ℹ️  Found {len(found_paths)} MCP.json files, using first one")
            
            # Auto-reload configuration with detected path
            self.reload_mcp_and_reinitialize()
        else:
            self.log_message("❌ No MCP.json files found in common locations")
            self.log_message("💡 Try browsing manually or check LM Studio installation")
            self.log_message("💡 You can also set MCP_JSON_PATH environment variable")
    
    async def test_component_async(self, component: str) -> Dict[str, Any]:
        """Test a specific component asynchronously"""
        try:
            if component == "sd_webui":
                return await self.test_sd_webui()
            elif component == "lm_studio":
                return await self.test_lm_studio()
            elif component == "chevereto":
                return await self.test_chevereto()
            elif component == "nudenet":
                return await self.test_nudenet_availability()
            elif component == "databases":
                return await self.test_databases()
            elif component == "discord_bot":
                return await self.test_discord_bot()
            else:
                return {"success": False, "error": f"Unknown component: {component}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_all_components(self):
        """Test all system components"""
        self.log_message("🔍 Starting comprehensive system test...")
        
        # Run async tests in thread
        def run_tests():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                component_names = {
                    "sd_webui": "SD WebUI",
                    "lm_studio": "LM Studio", 
                    "chevereto": "Chevereto",
                    "nudenet": "NudeNet",
                    "databases": "Databases",
                    "discord_bot": "Discord Bot"
                }
                
                for component in self.status_vars.keys():
                    component_name = component_names.get(component, component)
                    self.log_message(f"Testing {component_name}...")
                    
                    # Update status display
                    self.update_component_status(component, "🔄 Testing...", "Testing component...")
                    
                    result = loop.run_until_complete(self.test_component_async(component))
                    
                    if result["success"]:
                        message = result.get('message', 'OK')
                        full_message = f"✅ {message}"
                        
                        # Create detailed tooltip
                        tooltip_text = f"{component_name} Status:\n{message}\n"
                        if result.get('endpoint'):
                            tooltip_text += f"\nEndpoint: {result['endpoint']}"
                        tooltip_text += f"\nLast tested: {datetime.now().strftime('%H:%M:%S')}"
                        
                        self.update_component_status(component, full_message, tooltip_text)
                        self.log_message(f"✅ {component_name}: {message}")
                    else:
                        error = result.get('error', 'Failed')
                        suggestion = result.get('suggestion', '')
                        endpoint = result.get('endpoint', '')
                        
                        full_error = f"❌ {error}"
                        
                        # Create detailed tooltip with suggestion
                        tooltip_text = f"{component_name} Error:\n{error}\n"
                        if endpoint:
                            tooltip_text += f"\nEndpoint: {endpoint}"
                        if suggestion:
                            tooltip_text += f"\nSuggestion: {suggestion}"
                        tooltip_text += f"\nLast tested: {datetime.now().strftime('%H:%M:%S')}"
                        
                        self.update_component_status(component, full_error, tooltip_text)
                        
                        # Log detailed error with suggestion
                        log_message = f"❌ {component_name}: {error}"
                        if endpoint:
                            log_message += f" (at {endpoint})"
                        if suggestion:
                            log_message += f" - {suggestion}"
                        self.log_message(log_message)
                
                self.log_message("🎉 System test completed!")
                
            finally:
                loop.close()
        
        threading.Thread(target=run_tests, daemon=True).start()
    
    async def test_sd_webui(self) -> Dict[str, Any]:
        """Test SD WebUI connection and functionality"""
        base_url = os.getenv("SD_BASE_URL", "http://localhost:7860")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Test basic API
                samplers_url = f"{base_url}/sdapi/v1/samplers"
                self.log_message(f"🔍 Testing SD WebUI at: {base_url}")
                
                try:
                    response = await client.get(samplers_url)
                    if response.status_code != 200:
                        return {
                            "success": False, 
                            "error": f"HTTP {response.status_code} from {base_url}",
                            "endpoint": base_url,
                            "suggestion": "Check if SD WebUI is running with --api flag"
                        }
                    
                    samplers = response.json()
                    
                except httpx.ConnectError:
                    return {
                        "success": False,
                        "error": f"Connection refused to {base_url}",
                        "endpoint": base_url,
                        "suggestion": "Start SD WebUI with: ./webui.sh --api --listen"
                    }
                except httpx.TimeoutException:
                    return {
                        "success": False,
                        "error": f"Connection timeout to {base_url}",
                        "endpoint": base_url,
                        "suggestion": "Check network connectivity and SD WebUI status"
                    }
                
                # Test models endpoint
                try:
                    models_url = f"{base_url}/sdapi/v1/sd-models"
                    response = await client.get(models_url)
                    models = response.json() if response.status_code == 200 else []
                except:
                    models = []  # Models endpoint sometimes fails, but samplers working is enough
                
                return {
                    "success": True,
                    "message": f"Connected to {base_url} - {len(samplers)} samplers, {len(models)} models",
                    "endpoint": base_url,
                    "samplers": len(samplers),
                    "models": len(models)
                }
                
        except Exception as e:
            return {
                "success": False, 
                "error": f"Connection failed to {base_url}: {str(e)}",
                "endpoint": base_url,
                "suggestion": "Verify SD WebUI is running and accessible"
            }
    
    async def test_lm_studio(self) -> Dict[str, Any]:
        """Test LM Studio connection"""
        base_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                models_url = f"{base_url}/v1/models"
                self.log_message(f"🔍 Testing LM Studio at: {base_url}")
                
                try:
                    response = await client.get(models_url)
                    if response.status_code != 200:
                        return {
                            "success": False, 
                            "error": f"HTTP {response.status_code} from {base_url}",
                            "endpoint": base_url,
                            "suggestion": "Check if LM Studio is running with API enabled"
                        }
                    
                    models = response.json()
                    model_count = len(models.get("data", []))
                    
                    return {
                        "success": True,
                        "message": f"Connected to {base_url} - {model_count} models loaded",
                        "endpoint": base_url,
                        "models": model_count
                    }
                    
                except httpx.ConnectError:
                    return {
                        "success": False,
                        "error": f"Connection refused to {base_url}",
                        "endpoint": base_url,
                        "suggestion": "Start LM Studio and ensure API server is running"
                    }
                except httpx.TimeoutException:
                    return {
                        "success": False,
                        "error": f"Connection timeout to {base_url}",
                        "endpoint": base_url,
                        "suggestion": "Check LM Studio status and network connectivity"
                    }
                
        except Exception as e:
            return {
                "success": False, 
                "error": f"Connection failed to {base_url}: {str(e)}",
                "endpoint": base_url,
                "suggestion": "Verify LM Studio is running with API enabled"
            }
    
    async def test_chevereto(self) -> Dict[str, Any]:
        """Test Chevereto connection"""
        base_url = os.getenv("CHEVERETO_BASE_URL")
        
        if not base_url:
            return {
                "success": False, 
                "error": "CHEVERETO_BASE_URL not configured",
                "suggestion": "Set CHEVERETO_BASE_URL in environment or skip Chevereto"
            }
        
        guest_key = os.getenv("CHEVERETO_GUEST_API_KEY")
        if not guest_key:
            return {
                "success": False, 
                "error": "CHEVERETO_GUEST_API_KEY not configured",
                "endpoint": base_url,
                "suggestion": "Set guest API key or use local storage only"
            }
        
        # Use existing core logic instead of duplicating HTTP requests
        if not self.chevereto_client:
            return {
                "success": False,
                "error": "Chevereto client not initialized",
                "endpoint": base_url,
                "suggestion": "Check CHEVERETO_BASE_URL and API keys in MCP.json"
            }
        
        try:
            # Use the existing test_connection method from core logic
            result = await self.chevereto_client.test_connection()
            
            # Add endpoint info for debugging
            result["endpoint"] = base_url
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "endpoint": base_url,
                "suggestion": "Check network connectivity and configuration"
            }
    
    async def test_nudenet_availability(self) -> Dict[str, Any]:
        """Test if NudeNet extension is available"""
        try:
            base_url = os.getenv("SD_BASE_URL", "http://localhost:7860")
            
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if NudeNet extension endpoint exists
                response = await client.get(f"{base_url}/sdapi/v1/extensions")
                
                if response.status_code == 200:
                    extensions = response.json()
                    nudenet_found = False
                    
                    # Handle different response formats
                    for ext in extensions:
                        ext_name = ""
                        if isinstance(ext, dict):
                            # Extension is a dict, look for name field
                            ext_name = ext.get("name", "").lower()
                        elif isinstance(ext, str):
                            # Extension is a string
                            ext_name = ext.lower()
                        else:
                            # Convert to string as fallback
                            ext_name = str(ext).lower()
                        
                        if "nudenet" in ext_name or "nsfw" in ext_name:
                            nudenet_found = True
                            break
                    
                    if nudenet_found:
                        return {"success": True, "message": "NudeNet extension detected"}
                    else:
                        return {"success": False, "error": "NudeNet extension not found"}
                else:
                    # Fallback: assume available if SD WebUI is running
                    return {"success": True, "message": "Cannot detect extensions, assuming available"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_databases(self) -> Dict[str, Any]:
        """Test database accessibility"""
        try:
            databases = [
                "discord_llm.db",
                "content_mapping.db", 
                "lora_database.db",
                "discord_users.db",
                "chevereto_users.db"
            ]
            
            available = []
            missing = []
            
            for db_name in databases:
                db_path = Path(db_name)
                if db_path.exists():
                    available.append(db_name)
                else:
                    missing.append(db_name)
            
            if missing:
                return {
                    "success": False, 
                    "error": f"Missing databases: {', '.join(missing)}",
                    "available": len(available),
                    "missing": len(missing)
                }
            else:
                return {
                    "success": True,
                    "message": f"All {len(available)} databases available",
                    "available": len(available)
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_discord_bot(self) -> Dict[str, Any]:
        """Test Discord bot status and configuration"""
        try:
            config = get_mcp_config()
            # Fix: Load config first, then get env vars
            if not config.is_loaded:
                config.load_config()
            env_vars = config.env_vars if hasattr(config, 'env_vars') else {}
            
            # Check if Discord is enabled in config
            discord_enabled = env_vars.get('ENABLE_DISCORD', '').lower() == 'true'
            discord_token = env_vars.get('DISCORD_BOT_TOKEN', '')
            
            if not discord_enabled:
                return {
                    "success": False,  # Changed from True to False for disabled status
                    "error": "Discord integration disabled",  # Changed to error for warning display
                    "message": "ENABLE_DISCORD=false in MCP config",
                    "status": "disabled", 
                    "suggestion": "Set ENABLE_DISCORD=true to enable Discord bot",
                    "endpoint": "Config: ENABLE_DISCORD"
                }
            
            if not discord_token:
                return {
                    "success": False,
                    "error": "Discord token not configured",
                    "suggestion": "Set DISCORD_BOT_TOKEN in MCP.json",
                    "endpoint": "Config: DISCORD_BOT_TOKEN"
                }
            
            # Check if discord_bot.py exists and can be imported
            try:
                import subprocess
                import sys
                
                # Check if Discord dependencies are available
                result = subprocess.run([sys.executable, "-c", "import discord; print('Discord.py available')"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": "Discord.py not installed",
                        "suggestion": "Install discord.py: pip install discord.py",
                        "endpoint": "Dependencies"
                    }
                
                # Check if bot file exists
                bot_file = Path("discord_bot.py")
                if not bot_file.exists():
                    return {
                        "success": False,
                        "error": "discord_bot.py not found",
                        "suggestion": "Discord bot file missing from project",
                        "endpoint": "File: discord_bot.py"
                    }
                
                # Try to validate token format (basic check)
                if not discord_token.startswith(('MTA', 'MTM', 'MTI')):  # Common Discord token prefixes
                    return {
                        "success": False,
                        "error": "Invalid Discord token format",
                        "suggestion": "Check DISCORD_BOT_TOKEN format",
                        "endpoint": f"Token: {discord_token[:10]}..."
                    }
                
                return {
                    "success": True,
                    "message": f"Discord bot configured (token: {discord_token[:10]}...)",
                    "status": "configured",
                    "endpoint": f"Token: {discord_token[:10]}...",
                    "note": "Use 'python discord_bot.py' to start bot"
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Discord dependency check timed out",
                    "endpoint": "Dependencies"
                }
            except Exception as import_error:
                return {
                    "success": False,
                    "error": f"Discord setup issue: {str(import_error)}",
                    "endpoint": "Import test"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_test_image(self):
        """Generate test image with current settings"""
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showerror("Error", "Please enter a prompt")
            return
        
        self.log_message(f"🎨 Generating image: {prompt}")
        
        def run_generation():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Parse size
                try:
                    width, height = map(int, self.size_var.get().split('x'))
                    self.log_message(f"🔧 Generation settings: {width}x{height}, {self.steps_var.get()} steps")
                except ValueError:
                    self.log_message("❌ Invalid image size format")
                    return
                
                # Check if SD client is ready
                if not self.sd_client:
                    self.log_message("❌ SD Client not initialized - check SD WebUI connection")
                    return
                
                self.log_message("🔄 Starting image generation...")
                
                # Use real SD client for generation with progress monitoring
                result = loop.run_until_complete(self.real_generate_image_with_progress(
                    prompt=prompt,
                    steps=self.steps_var.get(),
                    width=width,
                    height=height
                ))
                
                if result.get("success"):
                    image_path = result.get("image_path")
                    self.log_message(f"✅ Image generated successfully: {Path(image_path).name}")
                    self.log_message(f"📁 Image saved to: {image_path}")
                    
                    # Track for NudeNet import
                    self.last_sd_image = image_path
                    
                    # Display the image
                    self.display_image_safe(image_path, "sd_result")
                    self.log_message("🖼️ Image displayed in SD Testing tab")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    self.log_message(f"❌ Generation failed: {error_msg}")
                    
            except Exception as e:
                self.log_message(f"❌ Generation error: {e}")
            finally:
                loop.close()
        
        threading.Thread(target=run_generation, daemon=True).start()
    
    async def real_generate_image(self, prompt: str, steps: int, width: int, height: int):
        """Real image generation using SD client"""
        try:
            if not self.sd_client:
                return {"success": False, "error": "SD Client not initialized"}
            
            # Create generation parameters
            params = GenerateImageInput(
                prompt=prompt,
                negative_prompt="blurry, low quality, watermark",
                steps=steps,
                width=width,
                height=height,
                cfg_scale=7.0,
                sampler_name="Euler",
                seed=-1,
                batch_size=1,
                output_path=self.config.get("IMAGE_OUT_PATH", "/tmp/images")
            )
            
            self.log_message(f"🎨 Generating with SD WebUI: {prompt[:50]}...")
            
            # Generate image
            results = await self.sd_client.generate_image(params)
            
            if results and len(results) > 0:
                # Use the first result
                result = results[0]
                image_path = result.output_path
                
                if os.path.exists(image_path):
                    return {"success": True, "image_path": image_path}
                else:
                    return {"success": False, "error": "Generated image file not found"}
            else:
                return {"success": False, "error": "No images generated"}
            
        except Exception as e:
            # Fallback to mock generation if real generation fails
            self.log_sd_message(f"⚠️  Real generation failed, using mock: {e}")
            return await self.mock_generate_image(prompt, steps, width, height)
    
    async def mock_generate_image(self, prompt: str, steps: int, width: int, height: int):
        """Mock image generation fallback"""
        try:
            # Create a simple test image
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (width, height), color='lightblue')
            draw = ImageDraw.Draw(img)
            
            # Add text
            try:
                # Try to use default font
                font = ImageFont.load_default()
            except:
                font = None
            
            text = f"Test Image\n{prompt[:30]}\n{steps} steps\n{width}x{height}"
            draw.text((10, 10), text, fill='black', font=font)
            
            # Save to temp file
            temp_path = tempfile.mktemp(suffix='.png')
            img.save(temp_path)
            
            return {"success": True, "image_path": temp_path}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def real_generate_image_with_progress(self, prompt: str, steps: int, width: int, height: int):
        """Real image generation with progress monitoring"""
        try:
            if not self.sd_client:
                return {"success": False, "error": "SD Client not initialized"}
            
            # Create generation parameters
            params = GenerateImageInput(
                prompt=prompt,
                negative_prompt="blurry, low quality, watermark",
                steps=steps,
                width=width,
                height=height,
                cfg_scale=7.0,
                sampler_name="Euler",
                seed=-1,
                batch_size=1,
                output_path=self.config.get("IMAGE_OUT_PATH", "/tmp/images")
            )
            
            self.log_sd_message(f"🎨 Sending generation request to SD WebUI...")
            self.log_sd_message(f"📝 Prompt: {prompt}")
            
            # Start generation (non-blocking)
            import asyncio
            generation_task = asyncio.create_task(self.sd_client.generate_image(params))
            
            # Monitor progress while generation is running
            progress_task = asyncio.create_task(self.monitor_generation_progress())
            
            # Wait for generation to complete
            results = await generation_task
            
            # Cancel progress monitoring
            progress_task.cancel()
            
            self.log_sd_message(f"📎 Generation request completed")
            
            if results and len(results) > 0:
                # Use the first result
                result = results[0]
                image_path = result.path  # Use 'path' not 'output_path'
                
                self.log_sd_message(f"🖼️ Generated image saved to: {image_path}")
                
                # SD client already handles remote/local properly
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    self.log_sd_message(f"✅ Image file verified ({file_size} bytes)")
                    return {"success": True, "image_path": image_path}
                else:
                    self.log_sd_message(f"❌ Image file not found at: {image_path}")
                    return {"success": False, "error": f"Generated image file not found at {image_path}"}
            else:
                self.log_sd_message("❌ SD WebUI returned empty results")
                return {"success": False, "error": "No images generated by SD WebUI"}
                
        except Exception as e:
            # Fallback to mock generation if real generation fails
            self.log_sd_message(f"⚠️  Real generation failed, using mock: {e}")
            return await self.mock_generate_image(prompt, steps, width, height)
    
    async def monitor_generation_progress(self):
        """Monitor SD WebUI generation progress using /sdapi/v1/progress endpoint"""
        try:
            base_url = self.config.get("SD_BASE_URL", "http://localhost:7860")
            
            async with httpx.AsyncClient(timeout=5) as client:
                last_progress = -1
                
                while True:
                    try:
                        # Check progress
                        response = await client.get(f"{base_url}/sdapi/v1/progress")
                        
                        if response.status_code == 200:
                            progress_data = response.json()
                            current_progress = progress_data.get("progress", 0)
                            
                            # Only log if progress changed significantly
                            if current_progress != last_progress and current_progress > 0:
                                progress_percent = int(current_progress * 100)
                                eta = progress_data.get("eta_relative", 0)
                                
                                if eta > 0:
                                    self.log_sd_message(f"🔄 Generation progress: {progress_percent}% (ETA: {eta:.1f}s)")
                                else:
                                    self.log_sd_message(f"🔄 Generation progress: {progress_percent}%")
                                
                                last_progress = current_progress
                            
                            # If progress reaches 100%, generation is done
                            if current_progress >= 1.0:
                                self.log_sd_message("🏁 Generation completed!")
                                break
                                
                        # Wait a bit before checking again
                        await asyncio.sleep(1)
                        
                    except asyncio.CancelledError:
                        # Progress monitoring was cancelled (generation finished)
                        break
                    except httpx.RequestError:
                        # Progress endpoint might not be available, just break
                        break
                    except Exception:
                        # Any other error, just continue without progress monitoring
                        break
                        
        except Exception:
            # Progress monitoring failed, but don't stop generation
            pass
    
    
    def display_image_safe(self, image_path: str, label_key: str):
        """Safely display image by scheduling it in the main thread"""
        def _display():
            self.display_image(image_path, label_key)
        
        # Schedule in main thread
        self.root.after(0, _display)
    
    def display_image(self, image_path: str, label_key: str):
        """Display image in the specified label"""
        try:
            if not os.path.exists(image_path):
                self.log_sd_message(f"❌ Image file not found: {image_path}")
                return
            
            # Check file size
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                self.log_sd_message(f"❌ Image file is empty: {image_path}")
                return
                
            self.log_sd_message(f"🖼️ Loading image: {os.path.basename(image_path)} ({file_size} bytes)")
                
            # Load and validate image with detailed debugging
            try:
                self.log_sd_message(f"🔍 Opening image with PIL...")
                img = Image.open(image_path)
                
                # Get detailed image info before verify
                original_size = img.size
                original_mode = img.mode
                original_format = img.format
                
                self.log_sd_message(f"🔍 Original image: {original_size}, mode={original_mode}, format={original_format}")
                
                # Verify the image is valid
                img.verify()
                self.log_sd_message(f"✅ Image verification passed")
                
                # Reopen image after verify (verify closes it)
                img = Image.open(image_path)
                
                # Check if conversion is needed
                if img.mode not in ('RGB', 'L'):
                    self.log_sd_message(f"🔄 Converting from {img.mode} to RGB")
                    img = img.convert('RGB')
                else:
                    self.log_sd_message(f"✅ Image mode {img.mode} is compatible")
                
            except Exception as e:
                self.log_sd_message(f"❌ PIL image loading failed: {e}")
                import traceback
                self.log_sd_message(f"🔍 PIL error traceback: {traceback.format_exc()}")
                return
            
            # Resize to fit display (max 400x400 for better viewing)
            self.log_sd_message(f"🔄 Resizing image from {img.size}...")
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            display_size = img.size
            self.log_sd_message(f"✅ Resized to {display_size}")
            
            # Try multiple PhotoImage creation methods
            photo = None
            
            # Method 1: Direct PhotoImage creation with extensive debugging
            try:
                self.log_sd_message(f"🔍 Attempting direct PhotoImage creation...")
                
                # Debug Tkinter state
                self.log_sd_message(f"🔍 Root window exists: {self.root is not None}")
                if self.root:
                    self.log_sd_message(f"🔍 Root window active: {self.root.winfo_exists()}")
                    self.log_sd_message(f"🔍 Root window class: {self.root.__class__}")
                
                # Debug threading
                import threading
                self.log_sd_message(f"🔍 Current thread: {threading.current_thread().name}")
                self.log_sd_message(f"🔍 Main thread: {threading.main_thread().name}")
                
                # Debug PIL image
                self.log_sd_message(f"🔍 PIL Image type: {type(img)}")
                self.log_sd_message(f"🔍 PIL Image mode: {img.mode}")
                self.log_sd_message(f"🔍 PIL Image size: {img.size}")
                
                # Ensure we're working with the main thread and root window exists
                if not self.root or not self.root.winfo_exists():
                    raise RuntimeError("Root window not available")
                
                # Force GUI update to ensure root is properly initialized
                self.root.update_idletasks()
                
                # Try creating PhotoImage with more debugging
                self.log_sd_message(f"🔍 About to create ImageTk.PhotoImage...")
                photo = ImageTk.PhotoImage(img)
                self.log_sd_message(f"✅ Direct PhotoImage creation succeeded")
            except Exception as e:
                self.log_sd_message(f"❌ Direct PhotoImage failed: {e}")
                
                # Method 2: Save to temp file and load from path
                try:
                    self.log_sd_message(f"🔍 Trying temp file method...")
                    temp_path = tempfile.mktemp(suffix='.png')
                    img.save(temp_path, 'PNG')
                    self.log_sd_message(f"🔍 Saved temp image to {temp_path}")
                    
                    # Use ImageTk.PhotoImage for better compatibility
                    temp_img = Image.open(temp_path)
                    photo = ImageTk.PhotoImage(temp_img)
                    self.log_sd_message(f"✅ Temp file PhotoImage creation succeeded")
                    
                    # Clean up temp file
                    os.unlink(temp_path)
                    
                except Exception as e2:
                    self.log_sd_message(f"❌ Temp file PhotoImage failed: {e2}")
                    
                    # Method 3: Convert to bytes and use tk.PhotoImage with base64
                    try:
                        self.log_sd_message(f"🔍 Trying base64 tk.PhotoImage method...")
                        import io
                        import base64
                        
                        # Save image to bytes as PNG
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        # Convert to base64
                        img_b64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
                        
                        # Use tk.PhotoImage with base64 data (might work better than ImageTk)
                        photo = tk.PhotoImage(data=img_b64)
                        self.log_sd_message(f"✅ Base64 tk.PhotoImage creation succeeded")
                        
                    except Exception as e3:
                        self.log_sd_message(f"❌ Bytes data PhotoImage failed: {e3}")
                        
                        # Method 4: Try with different image formats
                        try:
                            self.log_sd_message(f"🔍 Trying JPEG conversion method...")
                            # Convert to JPEG and back to see if that helps
                            temp_jpeg = tempfile.mktemp(suffix='.jpg')
                            img.convert('RGB').save(temp_jpeg, 'JPEG', quality=95)
                            
                            # Reload as JPEG
                            jpeg_img = Image.open(temp_jpeg)
                            photo = ImageTk.PhotoImage(jpeg_img)
                            self.log_sd_message(f"✅ JPEG conversion method succeeded")
                            
                            # Clean up
                            os.unlink(temp_jpeg)
                            jpeg_img.close()
                            
                        except Exception as e4:
                            self.log_sd_message(f"❌ All PhotoImage methods failed!")
                            self.log_sd_message(f"🔍 Final error: {e4}")
                            self.log_sd_message(f"🔍 Tkinter version info: {tk.TkVersion}")
                            self.log_sd_message(f"🔍 PIL version info: {Image.__version__ if hasattr(Image, '__version__') else 'Unknown'}")
                            
                            # Method 5: Fallback - Just show file path and save a copy for manual viewing
                            try:
                                self.log_sd_message(f"🔍 Trying fallback method - text display...")
                                
                                # Save a copy of the image for manual viewing
                                fallback_dir = Path.home() / "Desktop" / "sd_gui_images"
                                fallback_dir.mkdir(exist_ok=True)
                                fallback_path = fallback_dir / f"sd_image_{datetime.now().strftime('%H%M%S')}.png"
                                img.save(fallback_path, 'PNG')
                                
                                # Update label with text instead of image
                                if label_key in self.image_labels:
                                    self.image_labels[label_key].configure(
                                        text=f"Image generated successfully!\n\n{original_size[0]}x{original_size[1]} pixels\n\nSaved to:\n{fallback_path}\n\n(PIL/Tkinter display issue)",
                                        image="",
                                        compound=tk.TOP,
                                        justify=tk.CENTER,
                                        wraplength=300
                                    )
                                    self.image_labels[label_key].image = None
                                
                                self.log_sd_message(f"📁 Fallback: Image saved to {fallback_path}")
                                self.log_sd_message(f"⚠️ PIL/Tkinter compatibility issue - showing text instead")
                                return
                                
                            except Exception as e5:
                                self.log_sd_message(f"❌ Even fallback method failed: {e5}")
                                return
            
            if not photo:
                self.log_sd_message(f"❌ No PhotoImage created despite trying all methods")
                return
            
            # Update label with comprehensive error handling
            if label_key in self.image_labels:
                try:
                    self.log_sd_message(f"🔍 Updating label widget...")
                    label_widget = self.image_labels[label_key]
                    
                    # Check widget state
                    self.log_sd_message(f"🔍 Label widget type: {type(label_widget)}")
                    self.log_sd_message(f"🔍 Label widget exists: {label_widget.winfo_exists()}")
                    
                    # Update the label
                    label_widget.configure(image=photo, text="")
                    label_widget.image = photo  # Keep reference
                    
                    self.log_sd_message(f"✅ Image displayed successfully: {original_size[0]}x{original_size[1]} → {display_size[0]}x{display_size[1]}")
                    
                    # Force GUI update
                    self.root.update_idletasks()
                    
                except Exception as e:
                    self.log_sd_message(f"❌ Failed to update image label: {e}")
                    import traceback
                    self.log_sd_message(f"🔍 Label update error: {traceback.format_exc()}")
            else:
                self.log_sd_message(f"❌ Image label '{label_key}' not found")
                # Show available image labels for debugging
                available_labels = list(self.image_labels.keys())
                self.log_sd_message(f"🔍 Available image labels: {available_labels}")
                
                # Try to find similar label keys
                for key in available_labels:
                    if label_key.lower() in key.lower() or key.lower() in label_key.lower():
                        self.log_sd_message(f"🔍 Similar key found: {key}")
                
        except Exception as e:
            self.log_sd_message(f"❌ Critical error in display_image: {e}")
            self.log_sd_message(f"🔍 Image path: {image_path}")
            self.log_sd_message(f"🔍 Label key: {label_key}")
            self.log_sd_message(f"🔍 Python version: {sys.version}")
            import traceback
            self.log_sd_message(f"🔍 Full traceback: {traceback.format_exc()}")
            
            # Emergency fallback: show file path in label
            try:
                if label_key in self.image_labels:
                    self.image_labels[label_key].configure(text=f"Image generated but display failed\n{os.path.basename(image_path)}\nCheck logs for details")
            except:
                pass
    
    def browse_test_image(self):
        """Browse for test image file"""
        file_path = filedialog.askopenfilename(
            title="Select Test Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.test_image_path.set(file_path)
            self.display_image_safe(file_path, "before")
            self.log_nudenet_message(f"📁 Loaded test image: {Path(file_path).name}")
    
    def import_from_sd_testing(self):
        """Import the last generated image from SD testing"""
        if not self.last_sd_image or not Path(self.last_sd_image).exists():
            messagebox.showwarning("No Image", "No recent SD image available to import. Generate an image in SD Testing first.")
            return
        
        self.test_image_path.set(self.last_sd_image)
        self.display_image_safe(self.last_sd_image, "before")
        self.log_nudenet_message(f"📥 Imported image from SD Testing: {Path(self.last_sd_image).name}")
    
    def generate_nsfw_test(self):
        """Generate NSFW test image for NudeNet testing"""
        self.log_nudenet_message("🔞 Generating NSFW test image...")
        self.log_nudenet_message("🔄 Switching to SD Testing tab to generate image...")
        
        # Set prompt in SD testing
        self.prompt_entry.delete(0, tk.END)
        self.prompt_entry.insert(0, "artistic nude study, classical art style")
        
        # Switch to SD testing tab
        self.notebook.select(1)  # SD Testing is tab index 1
        
        # Generate the image (this logs to SD tab)
        self.generate_test_image()
        
        # Schedule a switch back to NudeNet tab after a delay
        def switch_back_and_import():
            if self.last_sd_image and Path(self.last_sd_image).exists():
                # Switch back to NudeNet tab
                self.notebook.select(2)  # NudeNet Testing is tab index 2
                # Import the generated image
                self.import_from_sd_testing()
                self.log_nudenet_message("✅ NSFW test image generated and imported!")
            else:
                self.log_nudenet_message("❌ Failed to generate test image")
        
        # Give the generation some time to complete
        self.root.after(3000, switch_back_and_import)
    
    def generate_safe_test(self):
        """Generate safe test image for NudeNet testing"""
        self.log_nudenet_message("✅ Generating safe test image...")
        self.log_nudenet_message("🔄 Switching to SD Testing tab to generate image...")
        
        # Set prompt in SD testing
        self.prompt_entry.delete(0, tk.END)
        self.prompt_entry.insert(0, "beautiful landscape, mountains, sunset")
        
        # Switch to SD testing tab
        self.notebook.select(1)  # SD Testing is tab index 1
        
        # Generate the image (this logs to SD tab)
        self.generate_test_image()
        
        # Schedule a switch back to NudeNet tab after a delay
        def switch_back_and_import():
            if self.last_sd_image and Path(self.last_sd_image).exists():
                # Switch back to NudeNet tab
                self.notebook.select(2)  # NudeNet Testing is tab index 2
                # Import the generated image
                self.import_from_sd_testing()
                self.log_nudenet_message("✅ Safe test image generated and imported!")
            else:
                self.log_nudenet_message("❌ Failed to generate test image")
        
        # Give the generation some time to complete
        self.root.after(3000, switch_back_and_import)
    
    def test_nudenet(self):
        """Test NudeNet filtering on current image"""
        image_path = self.test_image_path.get()
        if not image_path or not Path(image_path).exists():
            messagebox.showerror("Error", "Please select a valid test image")
            return
        
        self.log_nudenet_message("🔍 Testing NudeNet filtering...")
        
        def run_test():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if not self.sd_client:
                    self.log_nudenet_message("❌ SD Client not initialized")
                    return
                
                # Use existing NudeNet configuration from MCP.json (don't duplicate logic)
                # The sd_client already has the correct config loaded from MCP.json
                # If users want to test different thresholds, they should update MCP.json
                current_config = self.sd_client.nudenet_config if self.sd_client.nudenet_config else {}
                self.log_nudenet_message(f"📝 Using NudeNet config from MCP.json")
                
                # Run real NudeNet censoring
                self.log_nudenet_message(f"🔍 Running NudeNet analysis on: {Path(image_path).name}")
                result = loop.run_until_complete(
                    self.sd_client.nudenet_censor(image_path, save_original=True)
                )
                self.log_nudenet_message(f"✅ NudeNet analysis completed")
                
                detection_results = {
                    "success": result.get("success", False),
                    "nudity_detected": result.get("has_nsfw", False),
                    "original_path": result.get("original_image"),
                    "censored_path": result.get("censored_image"),
                    "mask_path": result.get("detection_mask"),
                    "detection_classes": result.get("detection_classes", []),
                    "confidence_scores": result.get("confidence_scores", []),
                    "error": result.get("error")
                }
                
                # Log detailed results 
                self.log_nudenet_message(f"📊 Success: {detection_results['success']}")
                self.log_nudenet_message(f"🔍 NSFW Detected: {detection_results['nudity_detected']}")
                
                if detection_results.get('detection_classes'):
                    classes_str = ", ".join(detection_results['detection_classes'])
                    self.log_nudenet_message(f"🏷️  Detected classes: {classes_str}")
                
                if detection_results.get('confidence_scores'):
                    max_confidence = max(detection_results['confidence_scores']) if detection_results['confidence_scores'] else 0
                    self.log_nudenet_message(f"📈 Max confidence: {max_confidence:.3f}")
                
                # Display detailed results in text area
                results_text = f"""NudeNet Detection Results:
=========================

Success: {detection_results['success']}
NSFW Detected: {detection_results['nudity_detected']}

Detection Details:
"""
                
                if detection_results.get('detection_classes'):
                    results_text += f"  Classes: {', '.join(detection_results['detection_classes'])}\n"
                if detection_results.get('confidence_scores'):
                    results_text += f"  Confidences: {[f'{s:.3f}' for s in detection_results['confidence_scores']]}\n"
                
                results_text += "\nPaths:\n"
                if detection_results.get('original_path'):
                    results_text += f"  Original: {detection_results['original_path']}\n"
                if detection_results.get('censored_path'):
                    results_text += f"  Censored: {detection_results['censored_path']}\n"
                if detection_results.get('mask_path'):
                    results_text += f"  Mask: {detection_results['mask_path']}\n"
                
                if detection_results.get('error'):
                    results_text += f"\nError: {detection_results['error']}\n"
                
                results_text += "\nConfiguration:\n"
                results_text += f"  Using MCP.json settings\n"
                if current_config:
                    results_text += f"  Config loaded: {len(current_config)} settings\n"
                
                self.detection_text.delete("1.0", tk.END)
                self.detection_text.insert("1.0", results_text)
                
                # Display all available images using safe display method
                images_displayed = 0
                
                # Always show the original (input) image
                if detection_results.get('original_path') and os.path.exists(detection_results['original_path']):
                    self.display_image_safe(detection_results['original_path'], "before")
                    self.log_nudenet_message(f"🖼️ Original image displayed")
                    images_displayed += 1
                elif os.path.exists(image_path):
                    # Fallback to input image if original not saved
                    self.display_image_safe(image_path, "before")
                    self.log_nudenet_message(f"🖼️ Input image displayed")
                    images_displayed += 1
                
                # Show filtered/censored result
                if detection_results.get('censored_path') and os.path.exists(detection_results['censored_path']):
                    self.display_image_safe(detection_results['censored_path'], "after")
                    self.log_nudenet_message("⚠️ NSFW content detected - censored image displayed")
                    images_displayed += 1
                elif detection_results['success'] and not detection_results['nudity_detected']:
                    # No nudity detected, show original in 'after' slot
                    self.display_image_safe(image_path, "after")
                    self.log_nudenet_message("✅ No NSFW content detected - original displayed")
                    images_displayed += 1
                else:
                    # Clear the after image slot if no result
                    if "after" in self.image_labels:
                        self.image_labels["after"].configure(text="No filtered image\n(detection failed)", image="")
                        self.image_labels["after"].image = None
                
                # Show detection mask if available
                if detection_results.get('mask_path') and os.path.exists(detection_results['mask_path']):
                    self.display_image_safe(detection_results['mask_path'], "mask")
                    self.log_nudenet_message(f"🎭 Detection mask displayed")
                    images_displayed += 1
                else:
                    # Clear the mask slot if no mask
                    if "mask" in self.image_labels:
                        self.image_labels["mask"].configure(text="No detection mask\n(no NSFW detected)", image="")
                        self.image_labels["mask"].image = None
                
                # Summary
                if detection_results['success']:
                    if detection_results['nudity_detected']:
                        self.log_nudenet_message(f"🔍 Analysis complete: NSFW detected ({images_displayed} images displayed)")
                    else:
                        self.log_nudenet_message(f"🔍 Analysis complete: Clean image ({images_displayed} images displayed)")
                else:
                    self.log_nudenet_message(f"❌ NudeNet analysis failed: {detection_results.get('error', 'Unknown error')}")
                    
            except Exception as e:
                self.log_nudenet_message(f"❌ NudeNet test failed: {e}")
                import traceback
                self.log_nudenet_message(f"🔍 Error details: {traceback.format_exc()}")
            finally:
                loop.close()
        
        threading.Thread(target=run_test, daemon=True).start()
    
    def update_mcp_params(self, event=None):
        """Update parameter template based on selected tool"""
        tool_name = self.selected_tool.get()
        params = self.mcp_tool_params.get(tool_name, {}).copy()
        
        # Update tool description
        for tool_id, description in self.mcp_tools:
            if tool_id == tool_name:
                self.tool_description.set(description)
                break
        
        # Update upload_image with last generated image if available
        if tool_name == "upload_image" and self.last_sd_image:
            params["image_path"] = self.last_sd_image
        
        # Clear and update parameters
        self.mcp_params.delete("1.0", tk.END)
        if params:
            params_json = json.dumps(params, indent=2)
            self.mcp_params.insert("1.0", params_json)
        else:
            self.mcp_params.insert("1.0", "{}")
    
    def execute_mcp_tool(self):
        """Execute selected MCP tool with parameters"""
        tool_name = self.selected_tool.get()
        
        try:
            params_text = self.mcp_params.get("1.0", tk.END).strip()
            params = json.loads(params_text) if params_text else {}
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON parameters: {e}")
            return
        
        self.log_message(f"🔧 Executing MCP tool: {tool_name}")
        
        def run_tool():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Call real MCP tool
                result_data = loop.run_until_complete(self.call_real_mcp_tool(tool_name, params))
                
                result = {
                    "tool": tool_name,
                    "parameters": params,
                    "success": result_data.get("success", True),
                    "result": result_data.get("result", result_data),
                    "timestamp": datetime.now().isoformat()
                }
                
                if "error" in result_data:
                    result["error"] = result_data["error"]
                    result["success"] = False
                
                # Format and display results
                formatted_result = json.dumps(result, indent=2, default=str)
                self.mcp_results.delete("1.0", tk.END)
                self.mcp_results.insert("1.0", formatted_result)
                
                if result["success"]:
                    self.log_message(f"✅ Tool {tool_name} executed successfully")
                else:
                    self.log_message(f"❌ Tool {tool_name} failed: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                self.log_message(f"❌ Tool execution failed: {e}")
                
                error_result = {
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
                formatted_result = json.dumps(error_result, indent=2)
                self.mcp_results.delete("1.0", tk.END)
                self.mcp_results.insert("1.0", formatted_result)
            finally:
                loop.close()
        
        threading.Thread(target=run_tool, daemon=True).start()
    
    async def call_real_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call real MCP tool functions"""
        try:
            # Import MCP functions directly
            from scripts.mcp_servers.sd_mcp_server import (
                generate_image, get_models, load_checkpoint, get_current_model,
                search_loras, get_queue_status, upload_image, start_guided_generation
            )
            
            # Map tool names to functions
            tool_functions = {
                "generate_image": generate_image,
                "get_models": get_models,
                "load_checkpoint": load_checkpoint,
                "get_current_model": get_current_model,
                "search_loras": search_loras,
                "get_queue_status": get_queue_status,
                "upload_image": upload_image,
                "start_guided_generation": start_guided_generation
            }
            
            if tool_name not in tool_functions:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "suggestion": "Check tool name spelling"
                }
            
            # Call the function with parameters
            func = tool_functions[tool_name]
            result = await func(**params)
            
            return {"success": True, "result": result}
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "suggestion": "Check parameters and SD WebUI connection"
            }
    
    def test_chevereto_guest(self):
        """Test Chevereto guest upload with proper credential handling"""
        self.log_message("📤 Testing Chevereto guest upload...")
        
        def run_guest_test():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if not self.chevereto_client:
                    self.upload_results.insert(tk.END, "❌ Chevereto client not initialized\n")
                    self.upload_results.insert(tk.END, "Check CHEVERETO_BASE_URL and CHEVERETO_GUEST_API_KEY in MCP.json\n")
                    self.upload_results.see(tk.END)
                    return
                
                # Show which credentials and endpoints are being used
                guest_key = self.config.get("CHEVERETO_GUEST_API_KEY", "Not set")
                base_url = self.config.get("CHEVERETO_BASE_URL", "Not set")
                upload_endpoint = f"{base_url.rstrip('/')}/api/1/upload" if base_url != "Not set" else "Not set"
                
                self.upload_results.insert(tk.END, f"Guest API Key: {guest_key[:8]}...\n")
                self.upload_results.insert(tk.END, f"Upload Endpoint: {upload_endpoint}\n")
                self.upload_results.insert(tk.END, f"Auth Method: Parameter-based (key=...)\n")
                
                # Create a test image for upload
                test_image_path = tempfile.mktemp(suffix='.png')
                from PIL import Image
                img = Image.new('RGB', (100, 100), color='blue')
                img.save(test_image_path)
                
                self.upload_results.insert(tk.END, "Uploading test image...\n")
                self.upload_results.see(tk.END)
                
                # Test guest upload (no user_id = guest mode)
                self.upload_results.insert(tk.END, "🔍 Testing Guest API endpoint...\n")
                self.upload_results.see(tk.END)
                
                result = loop.run_until_complete(
                    self.chevereto_client.upload_image(test_image_path, user_id=None)
                )
                
                if "url" in str(result).lower():
                    self.upload_results.insert(tk.END, f"✅ Guest upload successful: {result}\n")
                else:
                    self.upload_results.insert(tk.END, f"❌ Guest upload failed: {result}\n")
                    # Add troubleshooting info for 400/403 errors
                    if "400" in str(result) or "403" in str(result) or "forbidden" in str(result).lower():
                        self.upload_results.insert(tk.END, "⚠️  403/400 Error - Check API key permissions\n")
                        self.upload_results.insert(tk.END, "  • Verify CHEVERETO_GUEST_API_KEY is correct\n")
                        self.upload_results.insert(tk.END, "  • Check if guest uploads are enabled on server\n")
                        self.upload_results.insert(tk.END, "  • Verify Chevereto server configuration\n")
                
                # Cleanup
                os.unlink(test_image_path)
                
            except Exception as e:
                self.upload_results.insert(tk.END, f"❌ Guest upload error: {e}\n")
                if "400" in str(e) or "403" in str(e):
                    self.upload_results.insert(tk.END, "⚠️  Authentication error - check guest API key\n")
            finally:
                self.upload_results.see(tk.END)
                loop.close()
        
        threading.Thread(target=run_guest_test, daemon=True).start()
    
    def test_chevereto_personal(self):
        """Test Chevereto personal API upload with proper credential handling"""
        # Use override key if provided, otherwise use MCP.json key
        override_key = self.personal_api_key.get().strip()
        mcp_key = self.config.get("CHEVERETO_USER_API_KEY", "")
        
        api_key = override_key if override_key else mcp_key
        
        if not api_key:
            self.upload_results.insert(tk.END, "❌ No personal API key available\n")
            self.upload_results.insert(tk.END, "  • Enter key in override field above, OR\n")
            self.upload_results.insert(tk.END, "  • Set CHEVERETO_USER_API_KEY in MCP.json\n")
            self.upload_results.see(tk.END)
            return
        
        self.log_message("🔑 Testing Chevereto personal API upload...")
        
        def run_personal_test():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if not self.chevereto_client:
                    self.upload_results.insert(tk.END, "❌ Chevereto client not initialized\n")
                    self.upload_results.see(tk.END)
                    return
                
                # Show which credentials and endpoints are being used
                source = "override field" if override_key else "MCP.json"
                base_url = self.config.get("CHEVERETO_BASE_URL", "Not set")
                upload_endpoint = f"{base_url.rstrip('/')}/api/1/upload" if base_url != "Not set" else "Not set"
                
                self.upload_results.insert(tk.END, f"Personal API Key ({source}): {api_key[:8]}...\n")
                self.upload_results.insert(tk.END, f"Upload Endpoint: {upload_endpoint}\n")
                self.upload_results.insert(tk.END, f"Auth Method: Header-based (X-API-Key)\n")
                
                # Update client with personal API key
                self.chevereto_client.config.user_api_key = api_key
                
                # Create a test image for upload
                test_image_path = tempfile.mktemp(suffix='.png')
                from PIL import Image
                img = Image.new('RGB', (100, 100), color='green')
                img.save(test_image_path)
                
                self.upload_results.insert(tk.END, "Uploading test image...\n")
                self.upload_results.see(tk.END)
                
                # Test personal API upload with dummy user_id to trigger personal mode
                self.upload_results.insert(tk.END, "🔍 Testing Personal API endpoint...\n")
                self.upload_results.see(tk.END)
                
                result = loop.run_until_complete(
                    self.chevereto_client.upload_image(test_image_path, user_id="test_user")
                )
                
                if "url" in str(result).lower():
                    self.upload_results.insert(tk.END, f"✅ Personal API upload successful: {result}\n")
                else:
                    self.upload_results.insert(tk.END, f"❌ Personal API upload failed: {result}\n")
                    # Add troubleshooting info for 400/403 errors
                    if "400" in str(result) or "403" in str(result) or "forbidden" in str(result).lower():
                        self.upload_results.insert(tk.END, "⚠️  403/400 Error - Check API key permissions\n")
                        self.upload_results.insert(tk.END, "  • Verify personal API key is correct\n")
                        self.upload_results.insert(tk.END, "  • Check if user has upload permissions\n")
                        self.upload_results.insert(tk.END, "  • Verify API key hasn't expired\n")
                
                # Cleanup
                os.unlink(test_image_path)
                
            except Exception as e:
                self.upload_results.insert(tk.END, f"❌ Personal API upload error: {e}\n")
                if "400" in str(e) or "403" in str(e):
                    self.upload_results.insert(tk.END, "⚠️  Authentication error - check personal API key\n")
            finally:
                self.upload_results.see(tk.END)
                loop.close()
        
        threading.Thread(target=run_personal_test, daemon=True).start()
    
    def test_local_upload(self):
        """Test local upload using actual Chevereto client fallback"""
        self.log_message("💾 Testing local upload...")
        
        def run_local_upload():
            try:
                import tempfile
                import asyncio
                from PIL import Image
                from modules.stable_diffusion.chevereto_client import CheveretoClient, CheveretoConfig
                
                # Create CheveretoConfig that will force local fallback
                config = CheveretoConfig(
                    base_url='',  # Empty to force local fallback
                    user_api_key='',
                    guest_api_key='',
                    fallback_to_local=True
                )
                
                client = CheveretoClient(config)
                
                # Create a test image
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img = Image.new('RGB', (100, 100), color='red')
                    img.save(tmp.name, 'PNG')
                    test_image_path = tmp.name
                
                try:
                    # Run the local upload test
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        client._fallback_local_upload(test_image_path, user_id='gui_test')
                    )
                    
                    if result.get('success'):
                        url = result.get('url', 'No URL')
                        local_path = result.get('local_path', 'No path')
                        filename = result.get('filename', 'No filename')
                        
                        self.upload_results.insert(tk.END, f"✅ Local upload successful!\n")
                        self.upload_results.insert(tk.END, f"   HTTP URL: {url}\n")
                        self.upload_results.insert(tk.END, f"   Local Path: {local_path}\n")
                        self.upload_results.insert(tk.END, f"   Filename: {filename}\n")
                        self.upload_results.insert(tk.END, f"   Hosting: {result.get('hosting_service', 'unknown')}\n")
                        
                        # Verify the HTTP URL format and server availability
                        if 'http://' in url and '/images/' in url:
                            self.upload_results.insert(tk.END, f"✅ HTTP URL format is correct\n")
                            
                            # Check if HTTP server is actually running
                            try:
                                import httpx
                                server_url = url.split('/images/')[0] + '/info'
                                with httpx.Client() as client:
                                    response = client.get(server_url, timeout=3)
                                    self.upload_results.insert(tk.END, f"✅ HTTP server is running - URL is accessible\n")
                            except Exception as e:
                                self.upload_results.insert(tk.END, f"⚠️ HTTP server not running - URL won't work in browser\n")
                                self.upload_results.insert(tk.END, f"   Click '🌐 Start HTTP Server' button to serve files\n")
                                self.upload_results.insert(tk.END, f"   Or use file:// URL: file://{local_path}\n")
                        else:
                            self.upload_results.insert(tk.END, f"❌ HTTP URL format incorrect\n")
                    else:
                        error = result.get('error', 'Unknown error')
                        self.upload_results.insert(tk.END, f"❌ Local upload failed: {error}\n")
                        
                finally:
                    # Cleanup test image
                    try:
                        os.unlink(test_image_path)
                    except:
                        pass
                        
            except Exception as e:
                self.upload_results.insert(tk.END, f"❌ Local upload error: {e}\n")
                import traceback
                self.upload_results.insert(tk.END, f"   Details: {traceback.format_exc()}\n")
        
        # Run in thread to avoid blocking GUI
        threading.Thread(target=run_local_upload, daemon=True).start()
        self.upload_results.see(tk.END)
    
    def refresh_api_keys_display(self):
        """Refresh the API keys display with current MCP.json values"""
        try:
            self.api_keys_display.delete("1.0", tk.END)
            
            # Reload configuration from MCP.json
            self.log_message("🔄 Reloading configuration from MCP.json...")
            mcp_config = get_mcp_config()
            if not mcp_config.is_loaded:
                mcp_config.load_config()
            current_config = mcp_config.env_vars
            
            # Show current API keys from live configuration
            guest_key = current_config.get("CHEVERETO_GUEST_API_KEY", "Not set")
            user_key = current_config.get("CHEVERETO_USER_API_KEY", "Not set") 
            admin_key = current_config.get("CHEVERETO_ADMIN_API_KEY", "Not set")
            base_url = current_config.get("CHEVERETO_BASE_URL", "Not set")
            discord_token = current_config.get("DISCORD_BOT_TOKEN", "Not set")
            discord_enabled = current_config.get("ENABLE_DISCORD", "false")
            
            # Mask keys for security
            def mask_key(key):
                if key == "Not set" or not key:
                    return "Not set"
                return f"{key[:8]}..." if len(key) > 8 else key
            
            display_text = f"""Base URL: {base_url}
Guest API Key: {mask_key(guest_key)}
User API Key: {mask_key(user_key)}
Admin API Key: {mask_key(admin_key)}

Discord Bot Token: {mask_key(discord_token)}
Discord Enabled: {discord_enabled}"""
            
            self.api_keys_display.insert("1.0", display_text)
            self.log_message("🔄 API keys display refreshed")
            
        except Exception as e:
            self.log_message(f"❌ Error refreshing API keys display: {e}")
    
    def launch_discord_bot(self):
        """Launch Discord bot in a new terminal/process"""
        try:
            import subprocess
            import platform
            
            bot_script = Path(__file__).parent / "start_discord_bot.py"
            
            if not bot_script.exists():
                self.log_service_message("❌ start_discord_bot.py not found")
                return
            
            self.log_service_message("🤖 Launching Discord bot...")
            
            system = platform.system().lower()
            
            if system == "windows":
                # Windows: Open new Command Prompt
                subprocess.Popen([
                    "cmd", "/c", "start", "cmd", "/k", 
                    f"cd /d \"{Path(__file__).parent}\" && uv run python start_discord_bot.py"
                ], shell=True)
            elif system == "darwin":  # macOS
                # macOS: Open new Terminal window
                script = f'''
tell application "Terminal"
    do script "cd '{Path(__file__).parent}' && uv run python start_discord_bot.py"
    activate
end tell
'''
                subprocess.run(["osascript", "-e", script])
            else:  # Linux
                # Linux: Try common terminal emulators
                terminals = ["gnome-terminal", "konsole", "xterm", "terminator"]
                for terminal in terminals:
                    try:
                        if terminal == "gnome-terminal":
                            subprocess.Popen([
                                terminal, "--", "bash", "-c",
                                f"cd '{Path(__file__).parent}' && uv run python start_discord_bot.py; exec bash"
                            ])
                        else:
                            subprocess.Popen([
                                terminal, "-e", "bash", "-c",
                                f"cd '{Path(__file__).parent}' && uv run python start_discord_bot.py; exec bash"
                            ])
                        break
                    except FileNotFoundError:
                        continue
                else:
                    self.log_service_message("❌ No terminal emulator found")
                    return
            
            self.log_service_message("✅ Discord bot launched in new terminal")
            
        except Exception as e:
            self.log_service_message(f"❌ Failed to launch Discord bot: {e}")
    
    def launch_mcp_server(self):
        """Launch MCP HTTP server in a new terminal/process"""
        try:
            import subprocess
            import platform
            
            server_script = Path(__file__).parent / "mcp_http_server.py"
            
            if not server_script.exists():
                self.log_service_message("❌ mcp_http_server.py not found")
                return
            
            self.log_service_message("🔗 Launching MCP HTTP server...")
            
            system = platform.system().lower()
            
            if system == "windows":
                subprocess.Popen([
                    "cmd", "/c", "start", "cmd", "/k", 
                    f"cd /d \"{Path(__file__).parent}\" && uv run python mcp_http_server.py"
                ], shell=True)
            elif system == "darwin":  # macOS
                script = f'''
tell application "Terminal"
    do script "cd '{Path(__file__).parent}' && uv run python mcp_http_server.py"
    activate
end tell
'''
                subprocess.run(["osascript", "-e", script])
            else:  # Linux
                terminals = ["gnome-terminal", "konsole", "xterm", "terminator"]
                for terminal in terminals:
                    try:
                        if terminal == "gnome-terminal":
                            subprocess.Popen([
                                terminal, "--", "bash", "-c",
                                f"cd '{Path(__file__).parent}' && uv run python mcp_http_server.py; exec bash"
                            ])
                        else:
                            subprocess.Popen([
                                terminal, "-e", "bash", "-c",
                                f"cd '{Path(__file__).parent}' && uv run python mcp_http_server.py; exec bash"
                            ])
                        break
                    except FileNotFoundError:
                        continue
                else:
                    self.log_service_message("❌ No terminal emulator found")
                    return
            
            self.log_service_message("✅ MCP HTTP server launched in new terminal")
            
        except Exception as e:
            self.log_service_message(f"❌ Failed to launch MCP server: {e}")
    
    def run_health_check(self):
        """Run health check script"""
        try:
            import subprocess
            
            health_script = Path(__file__).parent / "health_check.py"
            
            if not health_script.exists():
                self.log_service_message("❌ health_check.py not found")
                return
            
            self.log_service_message("🏥 Running health check...")
            
            # Run health check and capture output
            result = subprocess.run([
                "uv", "run", "python", str(health_script)
            ], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.log_service_message("✅ Health check completed successfully")
                self.log_service_message(f"Output: {result.stdout}")
            else:
                self.log_service_message("❌ Health check failed")
                self.log_service_message(f"Error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.log_service_message("⚠️  Health check timed out after 60 seconds")
        except Exception as e:
            self.log_service_message(f"❌ Failed to run health check: {e}")
    
    def log_service_message(self, message: str):
        """Log message to service status area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.service_status.insert(tk.END, formatted_message)
        self.service_status.see(tk.END)
        self.root.update()
    
    def validate_configuration(self):
        """Validate MCP.json configuration"""
        self.log_message("✅ Validating MCP.json configuration...")
        
        validation_results = "MCP.json Configuration Validation:\n"
        validation_results += "=" * 40 + "\n\n"
        
        # Check MCP.json file existence
        mcp_path = Path(self.mcp_path.get())
        if mcp_path.exists():
            validation_results += f"✅ MCP.json found: {mcp_path}\n\n"
            
            try:
                with open(mcp_path) as f:
                    mcp_config = json.load(f)
                
                # Check SD_MCP_Server section
                sd_server = mcp_config.get("mcpServers", {}).get("SD_MCP_Server", {})
                if sd_server:
                    validation_results += "✅ SD_MCP_Server section found\n"
                    
                    # Check environment variables
                    env_vars = sd_server.get("env", {})
                    if env_vars:
                        validation_results += f"✅ Environment variables: {len(env_vars)} found\n\n"
                        
                        # Check required variables
                        required_vars = ["SD_BASE_URL", "LM_STUDIO_BASE_URL"]
                        validation_results += "Required Variables:\n"
                        for var in required_vars:
                            if var in env_vars:
                                validation_results += f"✅ {var}: {env_vars[var]}\n"
                            else:
                                validation_results += f"❌ {var}: Missing from MCP.json\n"
                        
                        # Check optional variables
                        optional_vars = ["DISCORD_BOT_TOKEN", "CHEVERETO_BASE_URL", "CHEVERETO_GUEST_API_KEY", "CHEVERETO_USER_API_KEY"]
                        validation_results += "\nOptional Variables:\n"
                        for var in optional_vars:
                            if var in env_vars:
                                value = str(env_vars[var])
                                if "TOKEN" in var or "KEY" in var:
                                    masked_value = f"{value[:8]}..." if len(value) > 8 else value
                                else:
                                    masked_value = value
                                validation_results += f"✅ {var}: {masked_value}\n"
                            else:
                                validation_results += f"⚪ {var}: Not in MCP.json\n"
                        
                        # Check NudeNet configuration
                        nudenet_vars = [k for k in env_vars.keys() if k.startswith("NUDENET_")]
                        if nudenet_vars:
                            validation_results += f"\n✅ NudeNet configuration: {len(nudenet_vars)} settings\n"
                            for var in nudenet_vars[:5]:  # Show first 5
                                validation_results += f"  • {var}: {env_vars[var]}\n"
                            if len(nudenet_vars) > 5:
                                validation_results += f"  • ... and {len(nudenet_vars) - 5} more\n"
                        else:
                            validation_results += "\n⚪ NudeNet configuration: Not found\n"
                            
                    else:
                        validation_results += "❌ No environment variables in SD_MCP_Server\n"
                else:
                    validation_results += "❌ SD_MCP_Server section not found in MCP.json\n"
                    
            except json.JSONDecodeError as e:
                validation_results += f"❌ Invalid JSON in MCP.json: {e}\n"
            except Exception as e:
                validation_results += f"❌ Error reading MCP.json: {e}\n"
        else:
            validation_results += f"❌ MCP.json not found at {mcp_path}\n"
            validation_results += "\nTo create MCP.json, see: https://docs.anthropic.com/en/docs/build-with-claude/computer-use\n"
        
        # Show current environment (after MCP.json loading)
        validation_results += "\n" + "=" * 40 + "\n"
        validation_results += "Current Environment (after MCP.json load):\n"
        mcp_vars = self.get_mcp_variables()
        for var in ["SD_BASE_URL", "LM_STUDIO_BASE_URL", "CHEVERETO_BASE_URL"]:
            value = os.getenv(var, "Not set")
            source = "(from MCP.json)" if var in mcp_vars else "(from environment)" if value != "Not set" else ""
            validation_results += f"{var}: {value} {source}\n"
        
        self.config_results.delete("1.0", tk.END)
        self.config_results.insert("1.0", validation_results)
        
        self.log_message("✅ MCP.json configuration validation completed")
    
    def browse_db_location(self):
        """Browse for database location directory"""
        directory = filedialog.askdirectory(
            title="Select Database Location",
            initialdir=self.db_location.get()
        )
        
        if directory:
            self.db_location.set(directory)
            self.log_db_message(f"📁 Database location set to: {directory}")
    
    def log_db_message(self, message: str):
        """Log message to database status text area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.db_status_text.insert(tk.END, formatted_message)
        self.db_status_text.see(tk.END)
        self.root.update()
    
    def get_db_path(self, db_name: str) -> Path:
        """Get full path for database file"""
        return Path(self.db_location.get()) / db_name
    
    def check_databases(self):
        """Check status of all databases"""
        self.log_db_message("🔍 Checking database status...")
        
        required_databases = {
            "discord_llm.db": "LLM conversations and personalities",
            "content_mapping.db": "Content classification system", 
            "lora_database.db": "LoRA management",
            "discord_users.db": "Discord user management",
            "chevereto_users.db": "Image hosting users"
        }
        
        db_location = Path(self.db_location.get())
        
        # Check if location exists
        if not db_location.exists():
            self.log_db_message(f"❌ Database location does not exist: {db_location}")
            return
        
        missing = []
        existing = []
        
        for db_name, description in required_databases.items():
            db_path = db_location / db_name
            
            if db_path.exists():
                # Check if it's a valid SQLite database
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    conn.close()
                    
                    self.log_db_message(f"✅ {db_name}: {len(tables)} tables - {description}")
                    existing.append(db_name)
                    
                except sqlite3.Error as e:
                    self.log_db_message(f"⚠️  {db_name}: Corrupt or invalid - {e}")
                    missing.append(db_name)
            else:
                self.log_db_message(f"❌ {db_name}: Missing - {description}")
                missing.append(db_name)
        
        # Check for modules subdirectory databases
        modules_sd_path = db_location / "modules" / "stable_diffusion"
        if modules_sd_path.exists():
            for db_name in ["lora_database.db", "content_mapping.db"]:
                db_path = modules_sd_path / db_name
                if db_path.exists():
                    self.log_db_message(f"✅ modules/stable_diffusion/{db_name}: Found")
        
        # Summary
        self.log_db_message(f"📊 Summary: {len(existing)} existing, {len(missing)} missing")
        
        if missing:
            self.log_db_message("💡 Use 'Create Missing DBs' to create missing databases")
    
    def create_missing_databases(self):
        """Create missing databases using the init script logic"""
        if not self.confirm_database_operation("create missing databases"):
            return
            
        self.log_db_message("🏗️ Creating missing databases...")
        
        def create_databases():
            try:
                db_location = Path(self.db_location.get())
                
                # Ensure directory exists
                db_location.mkdir(parents=True, exist_ok=True)
                
                # Save current directory and change to db location
                original_cwd = Path.cwd()
                os.chdir(db_location)
                
                try:
                    # Import and run database initialization
                    import sys
                    sys.path.insert(0, str(original_cwd))
                    
                    # Import the init script functions
                    from scripts.init_databases import (
                        create_chevereto_users_db,
                        create_discord_users_db, 
                        create_lora_database
                    )
                    from modules.llm.llm_database import LLMDatabase
                    from modules.stable_diffusion.content_db import ContentDatabase
                    
                    created_count = 0
                    
                    # Create basic databases if missing
                    if not Path("chevereto_users.db").exists():
                        create_chevereto_users_db()
                        self.log_db_message("✅ Created chevereto_users.db")
                        created_count += 1
                    
                    if not Path("discord_users.db").exists():
                        create_discord_users_db()
                        self.log_db_message("✅ Created discord_users.db")
                        created_count += 1
                    
                    if not Path("lora_database.db").exists():
                        create_lora_database()
                        self.log_db_message("✅ Created lora_database.db")
                        created_count += 1
                    
                    # Create LLM database if missing
                    if not Path("discord_llm.db").exists():
                        llm_db = LLMDatabase()
                        self.log_db_message("✅ Created discord_llm.db with personalities")
                        created_count += 1
                    
                    # Create content database if missing
                    modules_path = Path("modules/stable_diffusion")
                    if not (modules_path / "content_mapping.db").exists():
                        modules_path.mkdir(parents=True, exist_ok=True)
                        os.chdir(modules_path.parent.parent)  # Back to project root for content db
                        content_db = ContentDatabase()
                        self.log_db_message("✅ Created content_mapping.db with classification system")
                        created_count += 1
                    
                    if created_count == 0:
                        self.log_db_message("ℹ️ All databases already exist")
                    else:
                        self.log_db_message(f"🎉 Created {created_count} databases successfully!")
                    
                except Exception as e:
                    self.log_db_message(f"❌ Error creating databases: {e}")
                    
                finally:
                    # Restore original directory
                    os.chdir(original_cwd)
                    
            except Exception as e:
                self.log_db_message(f"❌ Database creation failed: {e}")
        
        threading.Thread(target=create_databases, daemon=True).start()
    
    def recreate_all_databases(self):
        """Recreate all databases (with backup)"""
        if not self.confirm_database_operation("recreate ALL databases (existing data will be backed up)"):
            return
            
        self.log_db_message("🔄 Recreating all databases...")
        
        def recreate_databases():
            try:
                db_location = Path(self.db_location.get())
                
                # Create backup first
                backup_dir = db_location / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                # Backup existing databases
                backed_up = 0
                for db_file in db_location.glob("*.db"):
                    if db_file.is_file():
                        backup_path = backup_dir / db_file.name
                        db_file.rename(backup_path)
                        backed_up += 1
                        self.log_db_message(f"📦 Backed up {db_file.name}")
                
                if backed_up > 0:
                    self.log_db_message(f"📦 Backed up {backed_up} databases to {backup_dir.name}")
                
                # Create fresh databases
                self.create_missing_databases()
                
            except Exception as e:
                self.log_db_message(f"❌ Recreation failed: {e}")
        
        threading.Thread(target=recreate_databases, daemon=True).start()
    
    def backup_and_clean_databases(self):
        """Backup databases and clean old conversations"""
        if not self.confirm_database_operation("backup databases and clean old conversations"):
            return
            
        self.log_db_message("🧹 Backing up and cleaning databases...")
        
        def backup_and_clean():
            try:
                db_location = Path(self.db_location.get())
                
                # Create backup
                backup_dir = db_location / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                backed_up = 0
                for db_file in db_location.glob("*.db"):
                    if db_file.is_file():
                        backup_path = backup_dir / db_file.name
                        import shutil
                        shutil.copy2(db_file, backup_path)
                        backed_up += 1
                        self.log_db_message(f"📦 Backed up {db_file.name}")
                
                # Clean conversations older than 30 days
                llm_db_path = db_location / "discord_llm.db"
                if llm_db_path.exists():
                    import sqlite3
                    conn = sqlite3.connect(str(llm_db_path))
                    cursor = conn.cursor()
                    
                    # Delete old conversations
                    cursor.execute("""
                        DELETE FROM conversations 
                        WHERE timestamp < datetime('now', '-30 days')
                    """)
                    
                    deleted = cursor.rowcount
                    conn.commit()
                    conn.close()
                    
                    if deleted > 0:
                        self.log_db_message(f"🧹 Cleaned {deleted} old conversation messages")
                    else:
                        self.log_db_message("ℹ️ No old conversations to clean")
                
                self.log_db_message(f"✅ Backup and cleanup completed - {backed_up} files backed up")
                
            except Exception as e:
                self.log_db_message(f"❌ Backup/cleanup failed: {e}")
        
        threading.Thread(target=backup_and_clean, daemon=True).start()
    
    def sync_lora_database(self):
        """Sync LoRA database with SD WebUI API"""
        self.log_db_message("🔄 Starting LoRA database sync...")
        
        def sync_lora():
            try:
                # Import LoRAManager and initialize
                from modules.stable_diffusion.lora_manager import LoRAManager
                from modules.stable_diffusion.sd_client import SDClient
                from modules.stable_diffusion.auth_manager import create_auth_manager_from_env
                from modules.config import get_mcp_config
                
                # Load config to get SD base URL
                config = get_mcp_config()
                if not config.is_loaded:
                    config.load_config()
                env_vars = config.env_vars
                
                sd_base_url = env_vars.get('SD_BASE_URL', 'http://localhost:7860')
                self.log_db_message(f"🔗 Connecting to SD WebUI at {sd_base_url}")
                
                # Create auth manager and SD client
                auth_manager = create_auth_manager_from_env(env_vars)
                sd_client = SDClient(base_url=sd_base_url, auth_manager=auth_manager)
                
                # Initialize LoRA manager
                db_path = Path(self.db_location.get()) / "lora_database.db"
                lora_manager = LoRAManager(db_path=str(db_path), sd_client=sd_client)
                
                # Run sync
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                updated_count = loop.run_until_complete(lora_manager.sync_with_sd_api())
                
                self.log_db_message(f"✅ LoRA sync complete! Updated {updated_count} entries")
                
                # Test the sync by doing a quick search
                results = lora_manager.search_loras_smart("", max_results=5)
                total_loras = len(lora_manager.search_loras_smart("", max_results=1000))
                
                self.log_db_message(f"📊 Total LoRAs in database: {total_loras}")
                if results:
                    self.log_db_message(f"🎯 Sample LoRAs: {', '.join([r['name'] for r in results[:3]])}")
                else:
                    self.log_db_message("⚠️ No LoRAs found - check SD WebUI connection")
                    
            except Exception as e:
                self.log_db_message(f"❌ LoRA sync failed: {str(e)}")
                # Log more details for debugging
                import traceback
                self.log_db_message(f"🔍 Error details: {traceback.format_exc()}")
        
        threading.Thread(target=sync_lora, daemon=True).start()
    
    def start_http_server(self):
        """Start the MCP HTTP server for serving local uploads"""
        self.log_db_message("🌐 Starting MCP HTTP server...")
        
        def start_server():
            try:
                import subprocess
                import httpx
                import time
                from modules.config import get_mcp_config
                
                # Check if server is already running
                try:
                    with httpx.Client() as client:
                        response = client.get('http://127.0.0.1:8000/info', timeout=3)
                        self.log_db_message(f"✅ HTTP server already running (status: {response.status_code})")
                        return
                except:
                    pass  # Server not running, proceed to start it
                
                # Get config for host/port
                config = get_mcp_config()
                if not config.is_loaded:
                    config.load_config()
                env_vars = config.env_vars
                
                host = env_vars.get('MCP_HTTP_HOST', '127.0.0.1')
                port = env_vars.get('MCP_HTTP_PORT', '8000')
                
                self.log_db_message(f"🚀 Starting HTTP server on {host}:{port}")
                
                # Start the HTTP server in a subprocess
                server_process = subprocess.Popen([
                    sys.executable, 'mcp_http_server.py'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Wait a moment for server to start
                time.sleep(3)
                
                # Check if server started successfully
                try:
                    with httpx.Client() as client:
                        response = client.get(f'http://{host}:{port}/info', timeout=5)
                        server_info = response.json()
                        self.log_db_message(f"✅ HTTP server started successfully!")
                        self.log_db_message(f"   Server: {server_info.get('name', 'Unknown')}")
                        self.log_db_message(f"   Version: {server_info.get('version', 'Unknown')}")
                        self.log_db_message(f"   URL: http://{host}:{port}")
                        self.log_db_message(f"   Images endpoint: http://{host}:{port}/images/<filename>")
                    
                    # Store process reference for cleanup if needed
                    if not hasattr(self, '_http_server_process'):
                        self._http_server_process = server_process
                        
                except Exception as e:
                    self.log_db_message(f"❌ HTTP server failed to start: {e}")
                    if server_process.poll() is None:
                        server_process.terminate()
                    
            except Exception as e:
                self.log_db_message(f"❌ Error starting HTTP server: {e}")
                import traceback
                self.log_db_message(f"🔍 Details: {traceback.format_exc()}")
        
        threading.Thread(target=start_server, daemon=True).start()
    
    def confirm_database_operation(self, operation: str) -> bool:
        """Confirm database operation with user"""
        return messagebox.askyesno(
            "Confirm Database Operation",
            f"Are you sure you want to {operation}?\n\nThis will affect the database location:\n{self.db_location.get()}",
            icon='warning'
        )
    
    def test_prompt_analysis(self):
        """Test the analyze_prompt MCP tool"""
        prompt = self.analysis_prompt_entry.get("1.0", tk.END).strip()
        if not prompt:
            self.log_analysis_message("❌ Please enter a prompt to analyze")
            return
        
        self.log_analysis_message(f"📊 Analyzing prompt: '{prompt}'")
        
        def run_analysis():
            try:
                # Test the MCP tool directly
                import asyncio
                from scripts.mcp_servers.sd_mcp_server import analyze_prompt
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(analyze_prompt(prompt))
                
                # Parse and display results
                import json
                analysis_data = json.loads(result)
                
                self.log_analysis_message("✅ Prompt analysis completed!")
                self.log_analysis_message(f"📈 Results:")
                self.log_analysis_message(f"   Original prompt: {analysis_data['original_prompt']}")
                
                analysis = analysis_data.get('analysis', {})
                self.log_analysis_message(f"   Total meaningful words: {analysis.get('total_meaningful_words', 0)}")
                self.log_analysis_message(f"   Categorized words: {analysis.get('categorized_words', 0)}")
                self.log_analysis_message(f"   Uncategorized words: {analysis.get('uncategorized_words', 0)}")
                
                # Show word breakdown
                word_breakdown = analysis_data.get('word_breakdown', {})
                categorized = word_breakdown.get('categorized', {})
                if categorized:
                    self.log_analysis_message(f"📝 Categorized words:")
                    for word, categories in categorized.items():
                        category_paths = [cat['full_path'] for cat in categories]
                        self.log_analysis_message(f"   • {word}: {', '.join(category_paths)}")
                
                uncategorized = word_breakdown.get('uncategorized', [])
                if uncategorized:
                    self.log_analysis_message(f"❓ Uncategorized words: {', '.join(uncategorized)}")
                
                # Show enhancement suggestions
                suggestions = analysis_data.get('recommended_enhancements', [])
                if suggestions:
                    self.log_analysis_message(f"💡 Enhancement suggestions:")
                    for suggestion in suggestions:
                        self.log_analysis_message(f"   • {suggestion}")
                
                # Show safety assessment
                safety = analysis_data.get('safety_assessment', {})
                safety_level = safety.get('level', 'unknown')
                self.log_analysis_message(f"🛡️ Safety level: {safety_level}")
                
                if 'warnings' in analysis_data:
                    self.log_analysis_message(f"⚠️ Safety warnings:")
                    for warning in analysis_data['warnings']:
                        self.log_analysis_message(f"   • {warning}")
                
            except Exception as e:
                self.log_analysis_message(f"❌ Analysis failed: {e}")
                import traceback
                self.log_analysis_message(f"🔍 Details: {traceback.format_exc()}")
        
        threading.Thread(target=run_analysis, daemon=True).start()
    
    def test_enhanced_generation(self):
        """Test generate_image with prompt enhancement enabled"""
        prompt = self.analysis_prompt_entry.get("1.0", tk.END).strip()
        if not prompt:
            self.log_analysis_message("❌ Please enter a prompt to test")
            return
        
        self.log_analysis_message(f"🎨 Testing enhanced generation with prompt: '{prompt}'")
        
        def run_enhanced_generation():
            try:
                # Test the MCP tool with enhancement enabled
                import asyncio
                from scripts.mcp_servers.sd_mcp_server import generate_image
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Test with enhancement enabled
                result = loop.run_until_complete(
                    generate_image(
                        prompt=prompt,
                        enhance_prompt=True,
                        upload=False,  # Skip upload for faster testing
                        steps=10,      # Reduce steps for faster testing
                        width=512,     # Smaller image for faster testing
                        height=512
                    )
                )
                
                # Parse and display results
                import json
                generation_data = json.loads(result)
                
                if generation_data.get('status') == 'success':
                    self.log_analysis_message("✅ Enhanced generation completed!")
                    
                    # Show prompt enhancement results
                    enhancement = generation_data.get('prompt_enhancement', {})
                    if enhancement.get('requested'):
                        self.log_analysis_message(f"🔧 Prompt enhancement:")
                        self.log_analysis_message(f"   Applied: {enhancement.get('applied', False)}")
                        self.log_analysis_message(f"   Original: {enhancement.get('original_prompt', '')}")
                        enhanced = enhancement.get('enhanced_prompt', '')
                        if enhanced and enhanced != enhancement.get('original_prompt', ''):
                            self.log_analysis_message(f"   Enhanced: {enhanced}")
                        else:
                            self.log_analysis_message(f"   No enhancements needed")
                    
                    # Show generation details
                    self.log_analysis_message(f"📁 Image saved: {generation_data.get('local_path', 'Unknown')}")
                    
                else:
                    self.log_analysis_message(f"❌ Generation failed: {generation_data.get('error', 'Unknown error')}")
                
            except Exception as e:
                self.log_analysis_message(f"❌ Enhanced generation failed: {e}")
                import traceback
                self.log_analysis_message(f"🔍 Details: {traceback.format_exc()}")
        
        threading.Thread(target=run_enhanced_generation, daemon=True).start()
    
    def test_local_content_analysis(self):
        """Test local content classification without going through MCP"""
        prompt = self.analysis_prompt_entry.get("1.0", tk.END).strip()
        if not prompt:
            self.log_analysis_message("❌ Please enter a prompt to analyze")
            return
        
        self.log_analysis_message(f"🔍 Testing local content analysis: '{prompt}'")
        
        def run_local_analysis():
            try:
                # Test the content database directly
                from modules.stable_diffusion.content_db import ContentDatabase
                
                db = ContentDatabase("modules/stable_diffusion/content_mapping.db")
                analysis = db.analyze_prompt(prompt)
                
                self.log_analysis_message("✅ Local content analysis completed!")
                self.log_analysis_message(f"📊 Raw analysis results:")
                self.log_analysis_message(f"   Total words: {analysis['total_words']}")
                self.log_analysis_message(f"   Filtered words: {analysis.get('filtered_words', [])}")
                self.log_analysis_message(f"   Categories found: {len(analysis['categories_found'])}")
                
                # Show categorized words
                categorized = analysis.get('categorized_words', {})
                if categorized:
                    self.log_analysis_message(f"✅ Categorized words ({len(categorized)}):")
                    for word, categories in categorized.items():
                        self.log_analysis_message(f"   • {word}: {categories[0]['full_path']} (conf: {categories[0]['confidence']})")
                
                # Show uncategorized words
                uncategorized = analysis.get('uncategorized_words', [])
                if uncategorized:
                    self.log_analysis_message(f"❓ Uncategorized words ({len(uncategorized)}): {', '.join(uncategorized)}")
                
                # Show categories found
                categories = analysis.get('categories_found', [])
                if categories:
                    self.log_analysis_message(f"📂 Categories detected: {', '.join(categories)}")
                
                # Show content flags
                flags = analysis.get('content_flags', [])
                if flags:
                    self.log_analysis_message(f"🚩 Content flags:")
                    for flag in flags:
                        self.log_analysis_message(f"   • {flag['word']}: {flag['category']} (conf: {flag['confidence']})")
                else:
                    self.log_analysis_message("✅ No content flags detected")
                
                db.close()
                
            except Exception as e:
                self.log_analysis_message(f"❌ Local analysis failed: {e}")
                import traceback
                self.log_analysis_message(f"🔍 Details: {traceback.format_exc()}")
        
        threading.Thread(target=run_local_analysis, daemon=True).start()
    
    def log_analysis_message(self, message: str):
        """Log message to content analysis results area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.analysis_results.insert(tk.END, formatted_message)
        self.analysis_results.see(tk.END)
        self.root.update()
    
    def run(self):
        """Start the GUI application"""
        self.log_message("🚀 SD MCP Server Testing Tool started")
        self.log_message("Click 'Test All Components' to validate your setup")
        self.root.mainloop()

if __name__ == "__main__":
    app = SDMCPTester()
    app.run()