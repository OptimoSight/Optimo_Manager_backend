# widget_routes.py - Complete NYX-style Interface Design v2

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import os

router = APIRouter()

@router.options("/vto-interface")
async def vto_interface_options():
    """Handle OPTIONS preflight for vto-interface"""
    return HTMLResponse(content="", status_code=200)

@router.get("/vto-interface")
async def vto_interface(
    category: str = Query(...),
    api_key: str = Query(...),
    color: str = Query(...),
    product_name: str = Query(...),
    color_name: str = Query("Default"),
    mode: str = Query("both"),
    colors: str = Query(None),
    color_names: str = Query(None),
    product_url: str = Query("https://example.com/product"),
    product_id: str = Query("default-product")
):
    """Serve the complete NYX-style VTO interface v2"""
    
    valid_categories = ['lipstick', 'eyeshadow', 'blush', 'foundation', 'mascara', 'eyeliner']
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid_categories}")
    
    if colors is None:
        colors = color
    if color_names is None:
        color_names = color_name
    
    interface_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Try-On - {product_name}</title>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #000000;
            min-height: 100vh;
            color: #ffffff;
            overflow: hidden;
        }}
        
        /* Main Container */
        .vto-container {{
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background: #000000;
            max-width: 100%;
            margin: 0 auto;
        }}
        
        /* Desktop specific styles */
        @media (min-width: 769px) {{
            .vto-container {{
                max-width: 600px;
                height: 100vh;
                box-shadow: 0 0 50px rgba(0, 0, 0, 0.5);
            }}
        }}
        
        /* Top Toolbar */
        .top-toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: rgba(0, 0, 0, 0.95);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
            z-index: 100;
            backdrop-filter: blur(10px);
        }}
        
        .toolbar-left {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        
        .toolbar-right {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        
        .toolbar-btn {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            color: #ffffff;
        }}
        
        .toolbar-btn:hover {{
            background: rgba(255, 255, 255, 0.2);
            transform: scale(1.05);
            border-color: #e879f9;
        }}
        
        .toolbar-btn.active {{
            background: #e879f9;
            border-color: #e879f9;
        }}
        
        /* Canvas Container */
        .canvas-container {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #1a1a1a;
            position: relative;
            overflow: hidden;
        }}
        
        .image-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        /* Comparison Slider */
        .comparison-container {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .comparison-image {{
            position: absolute;
            width: 100%;
            height: 100%;
            object-fit: cover;
            user-select: none;
        }}
        
        .after-image {{
            clip-path: inset(0 50% 0 0);
        }}
        
        .slider-line {{
            position: absolute;
            width: 3px;
            height: 100%;
            background: linear-gradient(180deg, transparent, #e879f9, transparent);
            left: 50%;
            top: 0;
            transform: translateX(-50%);
            z-index: 10;
            cursor: ew-resize;
            box-shadow: 0 0 20px rgba(232, 121, 249, 0.6);
            display: none;
        }}
        
        .slider-line.active {{
            display: block;
        }}
        
        .slider-handle {{
            position: absolute;
            width: 44px;
            height: 44px;
            background: #e879f9;
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(232, 121, 249, 0.8), 0 0 0 4px rgba(232, 121, 249, 0.3);
            cursor: ew-resize;
        }}
        
        .slider-handle::before,
        .slider-handle::after {{
            content: '';
            position: absolute;
            width: 0;
            height: 0;
            border-style: solid;
        }}
        
        .slider-handle::before {{
            left: 10px;
            border-width: 6px 8px 6px 0;
            border-color: transparent #ffffff transparent transparent;
        }}
        
        .slider-handle::after {{
            right: 10px;
            border-width: 6px 0 6px 8px;
            border-color: transparent transparent transparent #ffffff;
        }}
        
        /* Bottom Toolbar */
        .bottom-toolbar {{
            background: rgba(0, 0, 0, 0.98);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding: 20px 16px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            backdrop-filter: blur(10px);
            flex-shrink: 0;
        }}
        
        /* Tablet: Medium spacing */
        @media (min-width: 481px) and (max-width: 768px) {{
            .bottom-toolbar {{
                padding: 16px 14px;
                gap: 14px;
            }}
        }}
        
        /* Desktop: Compact toolbar */
        @media (min-width: 769px) {{
            .bottom-toolbar {{
                padding: 10px 12px;
                gap: 10px;
            }}
        }}
        
        .makeup-categories {{
            display: flex;
            justify-content: space-around;
            align-items: center;
            gap: 8px;
            padding: 0;
        }}
        
        /* Tablet: Medium gap */
        @media (min-width: 481px) and (max-width: 768px) {{
            .makeup-categories {{
                gap: 6px;
                padding: 0;
            }}
        }}
        
        /* Desktop: Compact gap */
        @media (min-width: 769px) {{
            .makeup-categories {{
                gap: 4px;
                padding: 0;
            }}
        }}
        
        .category-btn {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 5px 8px;
            border-radius: 10px;
            transition: all 0.3s ease;
            color: rgba(255, 255, 255, 0.5);
            flex: 1;
            min-width: 0;
        }}
        
        /* Tablet: Medium category buttons */
        @media (min-width: 481px) and (max-width: 768px) {{
            .category-btn {{
                padding: 5px 6px;
                gap: 4px;
            }}
        }}
        
        /* Desktop: Compact category buttons */
        @media (min-width: 769px) {{
            .category-btn {{
                padding: 6px 4px;
                gap: 4px;
            }}
        }}
        
        .category-btn:hover {{
            background: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.8);
        }}
        
        .category-btn.active {{
            color: #e879f9;
            background: rgba(232, 121, 249, 0.1);
        }}
        
        .category-icon {{
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .category-icon svg {{
            width: 28px;
            height: 28px;
        }}
        
        /* Tablet: Medium icons */
        @media (min-width: 481px) and (max-width: 768px) {{
            .category-icon {{
                width: 32px;
                height: 32px;
            }}
            
            .category-icon svg {{
                width: 24px;
                height: 24px;
            }}
        }}
        
        /* Desktop: Compact icons */
        @media (min-width: 769px) {{
            .category-icon {{
                width: 28px;
                height: 28px;
            }}
            
            .category-icon svg {{
                width: 22px;
                height: 22px;
            }}
        }}
        
        .category-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }}
        
        /* Tablet: Medium labels */
        @media (min-width: 481px) and (max-width: 768px) {{
            .category-label {{
                font-size: 10px;
            }}
        }}
        
        /* Desktop: Compact labels */
        @media (min-width: 769px) {{
            .category-label {{
                font-size: 9px;
            }}
        }}
        
        /* Control Tabs */
        .control-tabs {{
            display: flex;
            gap: 8px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }}
        
        .tab-btn {{
            flex: 1;
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.5);
            padding: 14px 16px;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.3s ease;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            letter-spacing: 0.5px;
        }}
        
        /* Tablet: Medium tabs */
        @media (min-width: 481px) and (max-width: 768px) {{
            .tab-btn {{
                padding: 12px 14px;
                font-size: 13px;
            }}
        }}
        
        /* Desktop: Compact tabs */
        @media (min-width: 769px) {{
            .tab-btn {{
                padding: 10px 12px;
                font-size: 12px;
            }}
        }}
        
        .tab-btn:hover {{
            color: rgba(255, 255, 255, 0.8);
        }}
        
        .tab-btn.active {{
            color: #e879f9;
            border-bottom-color: #e879f9;
        }}
        
        /* Shade Content */
        .shade-content {{
            display: none;
            padding: 1px 0;
        }}
        
        .shade-content.active {{
            display: block;
        }}
        
        /* Tablet: Medium padding */
        @media (min-width: 481px) and (max-width: 768px) {{
            .shade-content {{
                padding: 1px 0;
            }}
        }}
        
        /* Desktop: Compact padding */
        @media (min-width: 769px) {{
            .shade-content {{
                padding: 1px 0;
            }}
        }}
        
        .shade-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(65px, 1fr));
            gap: 14px;
            max-height: 180px;
            overflow-y: auto;
            padding: 4px;
        }}
        
        /* Tablet: Medium shade grid */
        @media (min-width: 481px) and (max-width: 768px) {{
            .shade-grid {{
                grid-template-columns: repeat(auto-fill, minmax(62px, 1fr));
                gap: 12px;
                max-height: 160px;
            }}
        }}
        
        /* Desktop: Compact shade grid */
        @media (min-width: 769px) {{
            .shade-grid {{
                grid-template-columns: repeat(auto-fill, minmax(58px, 1fr));
                gap: 10px;
                max-height: 120px;
            }}
        }}
        
        .shade-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            padding: 3px;
            border-radius: 8px;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }}
        
        .shade-item:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        
        .shade-item.active {{
            border-color: #e879f9;
            background: rgba(232, 121, 249, 0.1);
        }}
        
        .shade-swatch {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 3px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        }}
        
        .shade-item.active .shade-swatch {{
            border-color: #e879f9;
            box-shadow: 0 0 0 4px rgba(232, 121, 249, 0.2), 0 2px 8px rgba(0, 0, 0, 0.3);
        }}
        
        .shade-name {{
            font-size: 10px;
            color: rgba(255, 255, 255);
            text-align: center;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        /* Compare Content */
        .compare-content {{
            display: none;
            padding: 17px 0;
        }}
        
        .compare-content.active {{
            display: block;
        }}
        
        .compare-buttons {{
            display: flex;
            gap: 8px;
        }}
        
        .compare-btn {{
            flex: 1;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #ffffff;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
        }}
        
        .compare-btn:hover {{
            background: rgba(255, 255, 255, 0.15);
        }}
        
        .compare-btn.active {{
            background: #e879f9;
            border-color: #e879f9;
        }}
        
        /* Adjust Content */
        .adjust-content {{
            display: none;
            padding: 16px 0;
        }}
        
        .adjust-content.active {{
            display: block;
        }}
        
        .adjust-control {{
            margin-bottom: 16px;
        }}
        
        .adjust-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
        }}
        
        .adjust-slider {{
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: rgba(255, 255, 255, 0.1);
            outline: none;
            -webkit-appearance: none;
        }}
        
        .adjust-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #e879f9;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(232, 121, 249, 0.5);
        }}
        
        .adjust-slider::-moz-range-thumb {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #e879f9;
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 8px rgba(232, 121, 249, 0.5);
        }}
        
        /* Product Overlay */
        .product-overlay {{
            position: absolute;
            bottom: 1px;
            left: 16px;
            right: 16px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(20px);
            border-radius: 12px;
            padding: 6px 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            z-index: 20;
            transform: translateY(160px);
            opacity: 0;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid rgba(232, 121, 249, 0.3);
        }}
        
        .product-overlay.visible {{
            transform: translateY(0);
            opacity: 1;
        }}
        
        .product-info {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }}
        
        .product-details {{
            flex: 1;
            min-width: 0;
        }}
        
        .product-name {{
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .product-color {{
            font-size: 12px;
            color: #d1d5db;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .color-swatch {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            border: 2px solid rgba(255, 255, 255, 0.5);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }}
        
        .product-actions {{
            display: flex;
            gap: 8px;
        }}
        
        .action-btn {{
            background: linear-gradient(135deg, #e879f9, #c084fc);
            border: none;
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        
        .action-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(232, 121, 249, 0.4);
        }}
        
        .wishlist-btn {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            width: 36px;
            height: 36px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            color: #ffffff;
        }}
        
        .wishlist-btn:hover {{
            border-color: #f43f5e;
            background: rgba(244, 63, 94, 0.1);
        }}
        
        .wishlist-btn.active {{
            background: #f43f5e;
            border-color: #f43f5e;
        }}
        
        /* Loading Overlay */
        .loading-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            backdrop-filter: blur(10px);
        }}
        
        .loading-overlay.active {{
            display: flex;
        }}
        
        .loader-spinner {{
            width: 60px;
            height: 60px;
            border: 4px solid rgba(232, 121, 249, 0.2);
            border-top: 4px solid #e879f9;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }}
        
        .loader-text {{
            font-size: 16px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        
        .loader-subtext {{
            font-size: 14px;
            color: rgba(255, 255, 255, 0.6);
            text-align: center;
            max-width: 300px;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* Initial View */
        .initial-view {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 150;
            padding: 24px;
        }}
        
        .initial-view.hidden {{
            display: none;
        }}
        
        .initial-content {{
            text-align: center;
            max-width: 400px;
            width: 100%;
        }}
        
        .initial-logo {{
            font-size: 48px;
            margin-bottom: 16px;
        }}
        
        .initial-title {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #e879f9, #c084fc, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .initial-subtitle {{
            font-size: 14px;
            color: rgba(255, 255, 255, 0.6);
            margin-bottom: 40px;
            line-height: 1.6;
        }}
        
        .initial-buttons {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            width: 100%;
        }}
        
        .initial-btn {{
            background: linear-gradient(135deg, #e879f9, #c084fc);
            color: #ffffff;
            border: none;
            padding: 16px 24px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .initial-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(232, 121, 249, 0.4);
        }}
        
        .initial-btn.secondary {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .initial-btn.secondary:hover {{
            background: rgba(255, 255, 255, 0.15);
            box-shadow: 0 8px 25px rgba(255, 255, 255, 0.1);
        }}
        
        /* Terms and Conditions */
        .terms-container {{
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .terms-checkbox {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            text-align: left;
            margin-bottom: 16px;
        }}
        
        .terms-checkbox input[type="checkbox"] {{
            width: 20px;
            height: 20px;
            margin-top: 2px;
            cursor: pointer;
            accent-color: #e879f9;
            flex-shrink: 0;
        }}
        
        .terms-checkbox label {{
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
            line-height: 1.5;
            cursor: pointer;
        }}
        
        .terms-checkbox label a {{
            color: #e879f9;
            text-decoration: underline;
        }}
        
        .terms-checkbox label a:hover {{
            color: #c084fc;
        }}
        
        .terms-error {{
            font-size: 12px;
            color: #f43f5e;
            text-align: center;
            margin-top: 8px;
            display: none;
        }}
        
        .terms-error.show {{
            display: block;
        }}
        
        .hidden {{
            display: none !important;
        }}
        
        /* Scrollbar Styling */
        .shade-grid::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .shade-grid::-webkit-scrollbar-track {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }}
        
        .shade-grid::-webkit-scrollbar-thumb {{
            background: rgba(232, 121, 249, 0.5);
            border-radius: 3px;
        }}
        
        .shade-grid::-webkit-scrollbar-thumb:hover {{
            background: #e879f9;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .top-toolbar {{
                padding: 10px 12px;
            }}
            
            .toolbar-btn {{
                width: 36px;
                height: 36px;
            }}
            
            .bottom-toolbar {{
                padding: 0px;
                gap: 0px;
            }}
            
            .category-icon {{
                width: 28px;
                height: 28px;
            }}
            
            .category-label {{
                font-size: 9px;
            }}
            
            .tab-btn {{
                padding: 10px 12px;
                font-size: 11px;
            }}
            
            .shade-grid {{
                grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
                gap: 8px;
            }}
            
            .initial-title {{
                font-size: 24px;
            }}
            
            .initial-logo {{
                font-size: 36px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Loading Overlay -->
    <div id="loadingOverlay" class="loading-overlay">
        <div class="loader-spinner"></div>
        <div class="loader-text">Processing Your Photo</div>
        <div class="loader-subtext">This may take a few seconds. Please don't close the window.</div>
    </div>

    <!-- Main Container -->
    <div class="vto-container">
        <!-- Initial View -->
        <!-- In the initial view section, add a close button -->
        <div id="initialView" class="initial-view">
            <!-- Add close button to initial view -->
                <div style="position: absolute; top: 12px; right: 12px; z-index: 160;">
                    <button class="toolbar-btn" id="initialCloseBtn" title="Close" style="opacity: 0.7;">
                        <i data-lucide="x" style="width: 20px; height: 20px;"></i>
                    </button>
                </div>

            <div class="initial-content">
                <div class="initial-logo">💄</div>
                <h1 class="initial-title">Virtual Try-On</h1>
                <p class="initial-subtitle">See how {product_name} looks on you instantly. Upload a photo or use your camera for the best experience.</p>
                <div class="initial-buttons">
                    <button class="initial-btn" id="uploadBtn">
                        <i data-lucide="upload" style="width: 20px; height: 20px;"></i>
                        Upload Photo
                    </button>
                    <button class="initial-btn secondary" id="cameraBtn">
                        <i data-lucide="camera" style="width: 20px; height: 20px;"></i>
                        Use Camera
                    </button>
                    <button class="initial-btn secondary" id="modelBtn">
                        <i data-lucide="user" style="width: 20px; height: 20px;"></i>
                        Try on Model
                    </button>
                </div>
                
                <!-- Terms and Conditions -->
                <div class="terms-container">
                    <div class="terms-checkbox">
                        <input type="checkbox" id="termsCheckbox">
                        <label for="termsCheckbox">
                            I agree to the <a href="#" id="termsLink">Terms & Conditions</a> and <a href="#" id="privacyLink">Privacy Policy</a>. I consent to my photo being processed for virtual try-on purposes.
                        </label>
                    </div>
                    <div class="terms-error" id="termsError">
                        Please accept the terms and conditions to continue
                    </div>
                </div>
                
                <input type="file" id="photoUpload" accept="image/*" class="hidden">
            </div>
        </div>

        <!-- Top Toolbar -->
        <div class="top-toolbar">
            <div class="toolbar-left">
                <button class="toolbar-btn" id="homeBtn" title="Home">
                    <i data-lucide="home" style="width: 20px; height: 20px;"></i>
                </button>
                <button class="toolbar-btn" id="resetBtn" title="Reset">
                    <i data-lucide="rotate-ccw" style="width: 20px; height: 20px;"></i>
                </button>
                <button class="toolbar-btn" id="helpBtn" title="Help">
                    <i data-lucide="help-circle" style="width: 20px; height: 20px;"></i>
                </button>
            </div>
            <div class="toolbar-right">
                <button class="toolbar-btn" id="downloadBtn" title="Download">
                    <i data-lucide="download" style="width: 20px; height: 20px;"></i>
                </button>
                <button class="toolbar-btn" id="shareBtn" title="Share">
                    <i data-lucide="share-2" style="width: 20px; height: 20px;"></i>
                </button>
                <button class="toolbar-btn" id="closeBtn" title="Close">
                    <i data-lucide="x" style="width: 20px; height: 20px;"></i>
                </button>
            </div>
        </div>

        <!-- Canvas Container -->
        <div class="canvas-container">
            <div class="image-wrapper">
                <div class="comparison-container" id="comparisonContainer">
                    <img id="beforeImage" src="" alt="Before" class="comparison-image" style="display: none;">
                    <img id="afterImage" src="" alt="After" class="comparison-image after-image" style="display: none;">
                    <div class="slider-line" id="sliderLine">
                        <div class="slider-handle"></div>
                    </div>
                </div>
            </div>
            
            <!-- Product Overlay -->
            <div id="productOverlay" class="product-overlay">
                <div class="product-info">
                    <div class="product-details">
                        <div class="product-name">{product_name}</div>
                        <div class="product-color">
                            <div class="color-swatch" style="background-color: {color};"></div>
                            <span id="currentColorName">{color_name}</span>
                        </div>
                    </div>
                    <div class="product-actions">
                        <a href="{product_url}" target="_blank" class="action-btn">
                            <i data-lucide="shopping-bag" style="width: 14px; height: 14px;"></i>
                            Buy Now
                        </a>
                        <button class="wishlist-btn" id="wishlistBtn">
                            <i data-lucide="heart" style="width: 18px; height: 18px;"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bottom Toolbar -->
        <div class="bottom-toolbar">
            <!-- Makeup Categories -->
            <div class="makeup-categories">
                <button class="category-btn" data-category="looks" id="looksBtn">
                    <div class="category-icon">
                        <i data-lucide="sparkles" style="width: 24px; height: 24px;"></i>
                    </div>
                    <span class="category-label">Looks</span>
                </button>
                <button class="category-btn" data-category="foundation" id="foundationBtn">
                    <div class="category-icon">
                        <i data-lucide="droplet" style="width: 24px; height: 24px;"></i>
                    </div>
                    <span class="category-label">Base</span>
                </button>
                <button class="category-btn" data-category="contour" id="contourBtn">
                    <div class="category-icon">
                        <i data-lucide="circle-dot" style="width: 24px; height: 24px;"></i>
                    </div>
                    <span class="category-label">Contour</span>
                </button>
                <button class="category-btn" data-category="lips" id="lipsBtn">
                    <div class="category-icon">
                        <i data-lucide="smile" style="width: 24px; height: 24px;"></i>
                    </div>
                    <span class="category-label">Lips</span>
                </button>
                <button class="category-btn" data-category="eyes" id="eyesBtn">
                    <div class="category-icon">
                        <i data-lucide="eye" style="width: 24px; height: 24px;"></i>
                    </div>
                    <span class="category-label">Eyes</span>
                </button>
            </div>
            
            <!-- Control Tabs -->
            <div class="control-tabs">
                <button class="tab-btn active" id="shadesTab">Shades</button>
                <button class="tab-btn" id="compareTab">Compare</button>
            </div>
            
            <!-- Tab Contents -->
            <!-- Shades Tab -->
            <div id="shadesContent" class="shade-content active">
                <div class="shade-grid" id="shadeGrid">
                    <!-- Shades will be dynamically loaded here -->
                </div>
            </div>
            
            <!-- Compare Tab -->
            <div id="compareContent" class="compare-content">
                <div class="compare-buttons">
                    <button class="compare-btn" id="beforeBtn">Before</button>
                    <button class="compare-btn active" id="comparisonBtn">Split View</button>
                    <button class="compare-btn" id="afterBtn">After</button>
                </div>
            </div>
        </div>
    </div>

        <script>
        // ============ Global Variables ============
        const API_KEY = '{api_key}';
        const CATEGORY = '{category}';
        const COLOR = '{color}';
        const COLOR_NAME = '{color_name}';
        const PRODUCT_NAME = '{product_name}';
        const PRODUCT_ID = '{product_id}';
        const PRODUCT_URL = '{product_url}';
        
        // Parse multiple colors and names
        const COLORS_STRING = '{colors}';
        const COLOR_NAMES_STRING = '{color_names}';
        const COLORS = COLORS_STRING.split(',').map(c => c.trim());
        const COLOR_NAMES = COLOR_NAMES_STRING.split(',').map(c => c.trim());
        
        // Category mapping for automatic selection
        const CATEGORY_MAPPING = {{
            'lipstick': 'lips',
            'eyeshadow': 'eyes',
            'eyeliner': 'eyes',
            'mascara': 'eyes',
            'foundation': 'foundation',
            'blush': 'contour'
        }};
        
        // State
        let uploadedImageData = null;
        let afterImageData = null;
        let isProcessing = false;
        let isDragging = false;
        let sliderPosition = 50;
        let isWishlisted = false;
        let currentCategory = CATEGORY_MAPPING[CATEGORY] || 'foundation';
        let currentColorIndex = 0;
        let hasMakeupApplied = false;
        
        // NEW: Cache for processed images by color index
        let processedImagesCache = {{}};
        let isFirstApplication = true;

        // ============ Initialization ============
        document.addEventListener('DOMContentLoaded', function() {{
            initializeApp();
        }});

        function initializeApp() {{
            lucide.createIcons();
            initializeEventListeners();
            initializeSlider();
            loadShades();
            setActiveCategory();
            
            const savedWishlist = localStorage.getItem(`wishlist_${{PRODUCT_ID}}`);
            if (savedWishlist === 'true') {{
                toggleWishlist(true);
            }}
        }}
        
        document.getElementById('initialCloseBtn').addEventListener('click', closeVTO);
        
        function initializeEventListeners() {{
            // Initial view buttons
            document.getElementById('uploadBtn').addEventListener('click', startUploadMode);
            document.getElementById('cameraBtn').addEventListener('click', startCameraMode);
            document.getElementById('modelBtn').addEventListener('click', useModelPhoto);
            document.getElementById('termsLink').addEventListener('click', showTerms);
            document.getElementById('privacyLink').addEventListener('click', showPrivacy);
            document.getElementById('photoUpload').addEventListener('change', handleUpload);
            
            // Top toolbar buttons
            document.getElementById('homeBtn').addEventListener('click', goHome);
            document.getElementById('resetBtn').addEventListener('click', resetToOriginal);
            document.getElementById('helpBtn').addEventListener('click', showHelp);
            document.getElementById('downloadBtn').addEventListener('click', downloadImage);
            document.getElementById('shareBtn').addEventListener('click', shareImage);
            document.getElementById('closeBtn').addEventListener('click', closeVTO);
            
            // Bottom toolbar buttons
            document.getElementById('looksBtn').addEventListener('click', () => switchCategory('looks'));
            document.getElementById('foundationBtn').addEventListener('click', () => switchCategory('foundation'));
            document.getElementById('contourBtn').addEventListener('click', () => switchCategory('contour'));
            document.getElementById('lipsBtn').addEventListener('click', () => switchCategory('lips'));
            document.getElementById('eyesBtn').addEventListener('click', () => switchCategory('eyes'));
            
            // Tab buttons
            document.getElementById('shadesTab').addEventListener('click', () => switchTab('shades'));
            document.getElementById('compareTab').addEventListener('click', () => switchTab('compare'));
            
            // Compare buttons
            document.getElementById('beforeBtn').addEventListener('click', showBefore);
            document.getElementById('comparisonBtn').addEventListener('click', showComparison);
            document.getElementById('afterBtn').addEventListener('click', showAfter);
            
            // Wishlist button
            document.getElementById('wishlistBtn').addEventListener('click', () => toggleWishlist());
        }}

        // Set active category based on product type
        function setActiveCategory() {{
            const activeCategory = CATEGORY_MAPPING[CATEGORY] || 'foundation';
            
            // Remove active class from all category buttons
            document.querySelectorAll('.category-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            
            // Add active class to the correct category
            const activeCategoryBtn = document.querySelector('.category-btn[data-category="' + activeCategory + '"]');
            if (activeCategoryBtn) {{
                activeCategoryBtn.classList.add('active');
            }}
            
            currentCategory = activeCategory;
        }}

        // ============ Initial View Functions ============
        function startUploadMode() {{
            // Check if terms are accepted
            const termsCheckbox = document.getElementById('termsCheckbox');
            const termsError = document.getElementById('termsError');
            
            if (!termsCheckbox.checked) {{
                termsError.classList.add('show');
                setTimeout(() => {{
                    termsError.classList.remove('show');
                }}, 3000);
                return;
            }}
            
            document.getElementById('photoUpload').click();
        }}

        function startCameraMode() {{
            // Check if terms are accepted
            const termsCheckbox = document.getElementById('termsCheckbox');
            const termsError = document.getElementById('termsError');
            
            if (!termsCheckbox.checked) {{
                termsError.classList.add('show');
                setTimeout(() => {{
                    termsError.classList.remove('show');
                }}, 3000);
                return;
            }}
            
            alert('Camera mode: This would open the device camera for live try-on. Implementation requires camera API integration.');
        }}

        function useModelPhoto() {{
            // Check if terms are accepted
            const termsCheckbox = document.getElementById('termsCheckbox');
            const termsError = document.getElementById('termsError');
            
            if (!termsCheckbox.checked) {{
                termsError.classList.add('show');
                setTimeout(() => {{
                    termsError.classList.remove('show');
                }}, 3000);
                return;
            }}
            
            alert('Model mode: This would load a default model photo. Implementation requires default model images.');
        }}

        function showTerms(event) {{
            event.preventDefault();
            alert('Terms & Conditions:\\n\\n1. This virtual try-on tool is for preview purposes only\\n2. Colors may vary on different devices\\n3. Results are AI-generated approximations\\n4. Photos are processed securely and not stored\\n5. You must be 18+ or have parental consent\\n\\nFor full terms, visit our website.');
        }}

        function showPrivacy(event) {{
            event.preventDefault();
            alert('Privacy Policy:\\n\\n1. Your photos are processed in real-time\\n2. No photos are permanently stored on our servers\\n3. We do not share your images with third parties\\n4. Processing is done securely via encrypted connections\\n5. You can delete your session data at any time\\n\\nFor full privacy policy, visit our website.');
        }}

        // ============ Loading Functions ============
        function showLoading() {{
            document.getElementById('loadingOverlay').classList.add('active');
        }}

        function hideLoading() {{
            document.getElementById('loadingOverlay').classList.remove('active');
        }}

        // ============ Upload & Processing ============
        async function handleUpload(event) {{
            const file = event.target.files[0];
            if (!file) return;
            
            showLoading();
            
            try {{
                await processImageDirectly(file);
                document.getElementById('initialView').classList.add('hidden');
            }} catch (error) {{
                console.error('Upload error:', error);
                alert('Failed to process image. Please try again.');
            }} finally {{
                hideLoading();
            }}
        }}

        async function processImageDirectly(file) {{
            try {{
                const authMethods = [
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', file);
                            fd.append('org_id', '1');
                            fd.append('category', CATEGORY);
                            return fd;
                        }},
                        url: `/api/vto/upload?api_key=${{encodeURIComponent(API_KEY)}}`
                    }},
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', file);
                            fd.append('org_id', '1');
                            fd.append('category', CATEGORY);
                            fd.append('api_key', API_KEY);
                            return fd;
                        }},
                        url: '/api/vto/upload'
                    }}
                ];

                let response;
                for (const method of authMethods) {{
                    try {{
                        response = await fetch(method.url, {{
                            method: 'POST',
                            body: method.getFormData()
                        }});
                        if (response.ok) break;
                    }} catch (err) {{
                        continue;
                    }}
                }}

                if (!response || !response.ok) {{
                    throw new Error('Failed to process image');
                }}

                const result = await response.json();
                const processedImage = result.processed_image || result.image || result.data;
                
                if (!processedImage) {{
                    throw new Error('No processed image found in API response');
                }}

                let formattedImage = processedImage;
                if (!formattedImage.startsWith('data:image')) {{
                    formattedImage = `data:image/jpeg;base64,${{formattedImage}}`;
                }}

                uploadedImageData = formattedImage;
                document.getElementById('beforeImage').src = uploadedImageData;
                document.getElementById('beforeImage').style.display = 'block';
                document.getElementById('afterImage').src = uploadedImageData;
                document.getElementById('afterImage').style.display = 'block';
                
                // Auto-apply makeup
                await applyMakeup();
                
            }} catch (error) {{
                console.error('Processing error:', error);
                throw error;
            }}
        }}

        function base64ToBlob(base64Data) {{
            const base64WithoutPrefix = base64Data.split(',')[1] || base64Data;
            const byteCharacters = atob(base64WithoutPrefix);
            const byteArrays = [];
            
            for (let offset = 0; offset < byteCharacters.length; offset += 512) {{
                const slice = byteCharacters.slice(offset, offset + 512);
                const byteNumbers = new Array(slice.length);
                
                for (let i = 0; i < slice.length; i++) {{
                    byteNumbers[i] = slice.charCodeAt(i);
                }}
                
                byteArrays.push(new Uint8Array(byteNumbers));
            }}
            
            return new Blob(byteArrays, {{ type: 'image/jpeg' }});
        }}

        async function applyMakeup(colorIndex = 0) {{
            if (!uploadedImageData || isProcessing) return;
            
            // NEW: Check if we already have this shade cached
            if (processedImagesCache[colorIndex] && !isFirstApplication) {{
                // Use cached image for instant switching
                afterImageData = processedImagesCache[colorIndex];
                document.getElementById('afterImage').src = afterImageData;
                
                // Update color display
                const selectedColor = COLORS[colorIndex] || COLOR;
                const selectedColorName = COLOR_NAMES[colorIndex] || COLOR_NAME;
                document.getElementById('currentColorName').textContent = selectedColorName;
                document.querySelector('.product-color .color-swatch').style.backgroundColor = selectedColor;
                
                hasMakeupApplied = true;
                showAfter();
                return;
            }}
            
            isProcessing = true;
            
            // NEW: Only show loading for first application
            if (isFirstApplication) {{
                showLoading();
            }}
            
            try {{
                const blob = base64ToBlob(uploadedImageData);
                const selectedColor = COLORS[colorIndex] || COLOR;
                const selectedColorName = COLOR_NAMES[colorIndex] || COLOR_NAME;
                
                const authMethods = [
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', blob, 'processed-image.jpg');
                            fd.append('color', selectedColor);
                            fd.append('product_name', PRODUCT_NAME);
                            return fd;
                        }},
                        url: `/api/vto/apply_${{CATEGORY}}?api_key=${{encodeURIComponent(API_KEY)}}`
                    }},
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', blob, 'processed-image.jpg');
                            fd.append('color', selectedColor);
                            fd.append('product_name', PRODUCT_NAME);
                            fd.append('api_key', API_KEY);
                            return fd;
                        }},
                        url: `/api/vto/apply_${{CATEGORY}}`
                    }}
                ];

                let response;
                for (const method of authMethods) {{
                    try {{
                        response = await fetch(method.url, {{
                            method: 'POST',
                            body: method.getFormData()
                        }});
                        if (response.ok) break;
                    }} catch (err) {{
                        continue;
                    }}
                }}

                if (!response || !response.ok) {{
                    throw new Error('Failed to apply makeup');
                }}

                const imageBlob = await response.blob();
                const imageUrl = URL.createObjectURL(imageBlob);
                afterImageData = imageUrl;
                
                // NEW: Cache the processed image
                processedImagesCache[colorIndex] = imageUrl;
                
                document.getElementById('afterImage').src = imageUrl;
                
                // Update color display
                document.getElementById('currentColorName').textContent = selectedColorName;
                document.querySelector('.product-color .color-swatch').style.backgroundColor = selectedColor;
                
                // Auto-switch to shades tab and show after view
                document.querySelectorAll('.tab-btn').forEach((btn, i) => {{
                    btn.classList.toggle('active', i === 0);
                }});
                document.getElementById('shadesContent').classList.add('active');
                document.getElementById('compareContent').classList.remove('active');
                
                hasMakeupApplied = true;
                
                // Show after effect
                setTimeout(() => {{
                    showAfter();
                }}, 100);
                
                // NEW: Mark first application as complete
                isFirstApplication = false;
                
            }} catch (error) {{
                console.error('Makeup application error:', error);
                alert('Failed to apply makeup: ' + error.message);
            }} finally {{
                isProcessing = false;
                if (isFirstApplication) {{
                    hideLoading();
                }}
            }}
        }}

        // ============ Comparison Slider ============
        function initializeSlider() {{
            const sliderLine = document.getElementById('sliderLine');
            const container = document.getElementById('comparisonContainer');
            
            if (!sliderLine || !container) return;
            
            sliderLine.addEventListener('mousedown', startDragging);
            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', stopDragging);
            
            sliderLine.addEventListener('touchstart', startDragging);
            document.addEventListener('touchmove', drag);
            document.addEventListener('touchend', stopDragging);
        }}

        function startDragging(e) {{
            isDragging = true;
            e.preventDefault();
        }}

        function drag(e) {{
            if (!isDragging) return;
            
            const container = document.getElementById('comparisonContainer');
            const rect = container.getBoundingClientRect();
            
            let x;
            if (e.type.includes('touch')) {{
                x = e.touches[0].clientX - rect.left;
            }} else {{
                x = e.clientX - rect.left;
            }}
            
            sliderPosition = (x / rect.width) * 100;
            sliderPosition = Math.max(0, Math.min(100, sliderPosition));
            
            updateSliderPosition();
        }}

        function stopDragging() {{
            isDragging = false;
        }}

        function updateSliderPosition() {{
            const sliderLine = document.getElementById('sliderLine');
            const afterImage = document.getElementById('afterImage');
            
            sliderLine.style.left = sliderPosition + '%';
            afterImage.style.clipPath = `inset(0 ${{100 - sliderPosition}}% 0 0)`;
        }}

        function showComparisonMode() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.position = 'absolute';
            afterImage.style.position = 'absolute';
            
            beforeImage.style.display = 'block';
            afterImage.style.display = 'block';
            afterImage.style.clipPath = 'inset(0 50% 0 0)';
            document.getElementById('sliderLine').classList.add('active');
            updateSliderPosition();
            
            // Update compare buttons
            document.querySelectorAll('.compare-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('comparisonBtn').classList.add('active');
        }}

        function showBefore() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.display = 'block';
            afterImage.style.display = 'none';
            document.getElementById('sliderLine').classList.remove('active');
            document.getElementById('productOverlay').classList.remove('visible');
            
            // Update compare buttons
            document.querySelectorAll('.compare-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('beforeBtn').classList.add('active');
        }}

        function showComparison() {{
            showComparisonMode();
            document.getElementById('productOverlay').classList.add('visible');
            
            // Update compare buttons
            document.querySelectorAll('.compare-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('comparisonBtn').classList.add('active');
        }}

        function showAfter() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.display = 'none';
            afterImage.style.display = 'block';
            afterImage.style.clipPath = 'inset(0 0% 0 0)';
            document.getElementById('sliderLine').classList.remove('active');
            document.getElementById('productOverlay').classList.add('visible');
            
            // Update compare buttons
            document.querySelectorAll('.compare-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('afterBtn').classList.add('active');
        }}

        // ============ Tabs & Categories ============
        function switchTab(tabName) {{
            // Update tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            if (tabName === 'shades') {{
                document.getElementById('shadesTab').classList.add('active');
            }} else if (tabName === 'compare') {{
                document.getElementById('compareTab').classList.add('active');
            }}
            
            // Hide all content
            document.querySelectorAll('.shade-content, .compare-content').forEach(content => {{
                content.classList.remove('active');
            }});
            
            // Show selected content
            if (tabName === 'shades') {{
                document.getElementById('shadesContent').classList.add('active');
                // Show only after effect when in shades tab
                setTimeout(() => {{
                    showAfter();
                }}, 100);
            }} else if (tabName === 'compare') {{
                document.getElementById('compareContent').classList.add('active');
                // Show comparison view when in compare tab
                setTimeout(() => {{
                    showComparison();
                }}, 100);
            }}
        }}

        function switchCategory(category) {{
            currentCategory = category;
            
            // Update category buttons
            document.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(category + 'Btn').classList.add('active');
            
            console.log('Switched to category:', category);
            // In full implementation, this would load different products/shades
        }}

        // ============ Shades ============
        function loadShades() {{
            const shadeGrid = document.getElementById('shadeGrid');
            shadeGrid.innerHTML = '';
            
            COLORS.forEach((color, index) => {{
                const shadeName = COLOR_NAMES[index] || `Shade ${{index + 1}}`;
                
                const shadeItem = document.createElement('div');
                shadeItem.className = 'shade-item' + (index === currentColorIndex ? ' active' : '');
                shadeItem.addEventListener('click', () => selectShade(index));
                
                shadeItem.innerHTML = `
                    <div class="shade-swatch" style="background-color: ${{color}};"></div>
                    <div class="shade-name">${{shadeName}}</div>
                `;
                
                shadeGrid.appendChild(shadeItem);
            }});
        }}

        async function selectShade(index) {{
            // Check if user has uploaded a photo first
            if (!uploadedImageData) {{
                alert('Please upload a photo first to try on shades.');
                return;
            }}
            
            // Optimization - don't reapply if clicking the same shade that's already applied
            if (index === currentColorIndex && hasMakeupApplied) {{
                console.log('Same shade already applied, skipping reapplication');
                return;
            }}
            
            currentColorIndex = index;
            
            // Update UI
            document.querySelectorAll('.shade-item').forEach((item, i) => {{
                item.classList.toggle('active', i === index);
            }});
            
            // Apply new shade (this will use cache if available)
            await applyMakeup(index);
        }}

        // ============ Actions ============
        function toggleWishlist(forceState = null) {{
            const wishlistBtn = document.getElementById('wishlistBtn');
            
            if (forceState !== null) {{
                isWishlisted = forceState;
            }} else {{
                isWishlisted = !isWishlisted;
            }}
            
            if (isWishlisted) {{
                wishlistBtn.classList.add('active');
                localStorage.setItem(`wishlist_${{PRODUCT_ID}}`, 'true');
            }} else {{
                wishlistBtn.classList.remove('active');
                localStorage.setItem(`wishlist_${{PRODUCT_ID}}`, 'false');
            }}
            
            lucide.createIcons();
        }}

        function downloadImage() {{
            if (!afterImageData) {{
                alert('Please apply makeup first');
                return;
            }}
            
            const link = document.createElement('a');
            link.href = afterImageData;
            link.download = `vto-${{PRODUCT_NAME.replace(/\\s+/g, '-')}}-${{Date.now()}}.jpg`;
            link.click();
        }}

        function shareImage() {{
            if (!afterImageData) {{
                alert('Please apply makeup first');
                return;
            }}
            
            if (navigator.share) {{
                fetch(afterImageData)
                    .then(res => res.blob())
                    .then(blob => {{
                        const file = new File([blob], 'vto-result.jpg', {{ type: 'image/jpeg' }});
                        return navigator.share({{
                            title: 'Virtual Try-On Result',
                            text: `Check out this ${{PRODUCT_NAME}} look!`,
                            files: [file]
                        }});
                    }})
                    .catch(err => {{
                        console.error('Share error:', err);
                        alert('Sharing failed. Try downloading instead.');
                    }});
            }} else {{
                alert('Sharing not supported on this browser. Please use the download button instead.');
            }}
        }}

        function showHelp() {{
            const helpMessage = `Virtual Try-On Guide:

1. UPLOAD: Take or select a clear, front-facing photo
2. SHADES: Browse and select different shades
3. COMPARE: Use the slider to see before/after
4. ADJUST: Fine-tune intensity and opacity
5. SAVE: Download or share your look

Tips:
• Good lighting helps with accurate results
• Face the camera directly
• Remove glasses if trying eye makeup
• Try multiple shades to find your perfect match`;
            
            alert(helpMessage);
        }}

        function goHome() {{
            document.getElementById('initialView').classList.remove('hidden');
            
            // Reset everything
            uploadedImageData = null;
            afterImageData = null;
            processedImagesCache = {{}}; // NEW: Clear cache
            isFirstApplication = true; // NEW: Reset first application flag
            document.getElementById('beforeImage').src = '';
            document.getElementById('beforeImage').style.display = 'none';
            document.getElementById('afterImage').src = '';
            document.getElementById('afterImage').style.display = 'none';
            document.getElementById('productOverlay').classList.remove('visible');
            document.getElementById('sliderLine').classList.remove('active');
            
            hasMakeupApplied = false;
        }}

        function resetToOriginal() {{
            if (!uploadedImageData) {{
                alert('Please upload a photo first');
                return;
            }}
            
            // Reset to original uploaded image
            afterImageData = null;
            document.getElementById('afterImage').src = uploadedImageData;
            document.getElementById('productOverlay').classList.remove('visible');
            
            hasMakeupApplied = false;
            
            // Reset to first shade (but don't reapply makeup)
            currentColorIndex = 0;
            document.querySelectorAll('.shade-item').forEach((item, i) => {{
                item.classList.toggle('active', i === 0);
            }});
            
            // Switch to shades tab and show after view
            document.querySelectorAll('.tab-btn').forEach((btn, i) => {{
                btn.classList.toggle('active', i === 0);
            }});
            document.getElementById('shadesContent').classList.add('active');
            document.getElementById('compareContent').classList.remove('active');
            
            showBefore();
        }}

        function closeVTO() {{
            window.parent.postMessage({{action: 'close'}}, '*');
            
            document.body.style.transition = 'opacity 0.3s ease';
            document.body.style.opacity = '0';
            
            setTimeout(() => {{
                uploadedImageData = null;
                afterImageData = null;
                processedImagesCache = {{}}; // NEW: Clear cache
                isProcessing = false;
                document.body.style.opacity = '1';
                document.body.style.transition = '';
            }}, 300);
        }}
    </script>
</body>
</html>
    """
    return HTMLResponse(content=interface_html)