# widget_routes.py - Fixed with multiple auth attempts

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
    color_names: str = Query(None)
):
    """Serve the main VTO interface with upload/camera options"""
    
    valid_categories = ['lipstick', 'eyeshadow', 'blush', 'foundation', 'mascara', 'eyeliner']
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid_categories}")
    
    # Handle None values
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
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #6d28d9;
            min-height: 100vh;
            color: #1f2937;
        }}
        .vto-popup {{
            background: #d4bbfc;
            border-radius: 16px;
            padding: 32px 24px;
            max-width: 400px;
            margin: 0 auto;
            position: relative;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}
        .vto-instructions {{
            background: #1f2937;
            border-radius: 16px;
            padding: 32px 24px;
            max-width: 400px;
            margin: 0 auto;
            position: relative;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            color: white;
        }}
        .vto-tryon {{
            border-radius: 16px;
            padding: 16px;
            max-width: 600px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            height: 90vh;
        }}
        .vto-image-container {{
            flex: 1;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
            background: #1f2937;
        }}
        
        .image-comparison-container {{
            position: relative;
            width: 100%;
            height: 100%;
            overflow: hidden;
            user-select: none;
        }}
        .comparison-image {{
            position: relative;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .after-image {{
            clip-path: inset(0 50% 0 0);
        }}
        .slider-line {{
            position: absolute;
            width: 3px;
            height: 100%;
            background: white;
            left: 50%;
            top: 0;
            transform: translateX(-50%);
            z-index: 10;
            cursor: ew-resize;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
            display: none;
        }}
        .slider-line.active {{
            display: block;
        }}
        .slider-handle {{
            position: absolute;
            width: 40px;
            height: 40px;
            background: white;
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
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
            left: 8px;
            border-width: 6px 8px 6px 0;
            border-color: transparent #6d28d9 transparent transparent;
        }}
        .slider-handle::after {{
            right: 8px;
            border-width: 6px 0 6px 8px;
            border-color: transparent transparent transparent #6d28d9;
        }}
        
        .vto-apply-btn {{
            background: linear-gradient(135deg, #e879f9, #c084fc);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            margin-top: 20px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(183, 148, 246, 0.3);
        }}
        .vto-apply-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(183, 148, 246, 0.5);
        }}
        .vto-apply-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}
        .button-group {{
            display: flex;
            gap: 12px;
            margin-top: 16px;
        }}
        .vto-toggle-btn {{
            flex: 1;
            background: #1f2937;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        .vto-toggle-btn:hover {{
            background: #374151;
        }}
        .hidden {{
            display: none;
        }}
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div id="initial-view" class="vto-popup">
        <div class="text-center mb-6">
            <h2 class="text-sm font-bold uppercase text-gray-800">Professional Makeup</h2>
            <h1 class="text-3xl font-bold text-gray-800">Virtual Try On.</h1>
            <div class="flex justify-end items-center mt-2 pr-4">
                <i data-lucide="camera" class="text-gray-800 mr-2"></i>
                <span class="text-xl font-bold text-gray-800 rotate-[-10deg]">TRY ME ON!</span>
                <i data-lucide="corner-down-left" class="text-gray-800 ml-2"></i>
            </div>
            <p class="text-sm text-gray-600 mt-6">For the best virtual try-on experience, please use Safari on iOS and Chrome on Android.</p>
        </div>
        <div class="space-y-3">
            <button id="selfie-button" class="w-full py-3 bg-pink-500 text-gray-900 font-semibold rounded text-center" onclick="startSelfieMode()">SELFIE MODE</button>
            <button id="upload-button" class="w-full py-3 bg-gray-900 text-white font-semibold rounded text-center" onclick="showInstructions()">UPLOAD PHOTO</button>
            <button id="model-button" class="w-full py-3 bg-gray-900 text-white font-semibold rounded text-center" onclick="useModel()">USE MODEL</button>
        </div>
    </div>

    <div id="instructions-view" class="vto-instructions hidden">
        <button class="absolute top-2 left-2 text-xl font-bold text-white" onclick="backToInitial()">←</button>
        <button class="absolute top-2 right-2 text-xl font-bold text-white" onclick="closeVTO()">×</button>
        <h1 class="text-2xl font-bold text-center mb-6">PHOTO INSTRUCTIONS</h1>
        <div class="space-y-6">
            <div class="flex items-start gap-3">
                <i data-lucide="user-plus" class="text-white flex-shrink-0"></i>
                <p>Use a photo that is of the face straight on.</p>
            </div>
            <div class="flex items-start gap-3">
                <i data-lucide="glasses" class="text-white flex-shrink-0"></i>
                <p>Make sure nothing is obstructing the face.</p>
            </div>
            <div class="flex items-start gap-3">
                <i data-lucide="lightbulb" class="text-white flex-shrink-0"></i>
                <p>Make sure that the lighting is not too dim or overexposed.</p>
            </div>
        </div>
        <button class="w-full py-3 bg-white text-gray-900 font-semibold rounded mt-8" onclick="triggerUpload()">UPLOAD PHOTO</button>
        <input type="file" id="photoUpload" accept="image/*" class="hidden" onchange="handleUpload(event)">
    </div>

    <div id="tryon-view" class="vto-tryon hidden">
        <button class="absolute top-2 left-2 text-xl font-bold text-white z-30" onclick="backToInitial()">←</button>
        <button class="absolute top-2 right-2 text-xl font-bold text-white z-30" onclick="closeVTO()">×</button>
        
        <div class="vto-image-container">
            <div class="image-comparison-container" id="comparisonContainer">
                <img id="beforeImage" src="" alt="Before" class="comparison-image">
                <img id="afterImage" src="" alt="After" class="comparison-image after-image">
                <div class="slider-line" id="sliderLine">
                    <div class="slider-handle"></div>
                </div>
            </div>
        </div>
        
        <button class="vto-apply-btn" id="apply-makeup-btn" onclick="handleApplyMakeup()">
            Apply Makeup
        </button>
        
        <div class="button-group hidden" id="toggleButtons">
            <button class="vto-toggle-btn" onclick="showBefore()">Before</button>
            <button class="vto-toggle-btn" onclick="showComparison()">Compare</button>
            <button class="vto-toggle-btn" onclick="showAfter()">After</button>
        </div>
    </div>

    <script>
        lucide.createIcons();

        const API_KEY = '{api_key}';
        const CATEGORY = '{category}';

        if ('{mode}' !== 'both') {{
            if ('{mode}' === 'live') {{
                document.getElementById('upload-button').style.display = 'none';
                document.getElementById('model-button').style.display = 'none';
            }} else if ('{mode}' === 'upload') {{
                document.getElementById('selfie-button').style.display = 'none';
                document.getElementById('model-button').style.display = 'none';
            }}
        }}

        let uploadedImageData = null;
        let afterImageData = null;
        let isProcessing = false;
        let isDragging = false;
        let sliderPosition = 50;
        let currentView = 'before';

        window.addEventListener('load', function() {{
            initializeSlider();
        }});

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

        function showBefore() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.position = 'relative';
            afterImage.style.position = 'relative';
            
            beforeImage.style.display = 'block';
            afterImage.style.display = 'none';
            document.getElementById('sliderLine').classList.remove('active');
            
            currentView = 'before';
        }}

        function showComparison() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.position = 'absolute';
            afterImage.style.position = 'relative';
            
            beforeImage.style.display = 'block';
            afterImage.style.display = 'block';
            afterImage.style.clipPath = `inset(0 ${{100 - sliderPosition}}% 0 0)`;
            document.getElementById('sliderLine').classList.add('active');
            updateSliderPosition();
            
            currentView = 'comparison';
        }}

        function showAfter() {{
            const beforeImage = document.getElementById('beforeImage');
            const afterImage = document.getElementById('afterImage');
            
            beforeImage.style.position = 'relative';
            afterImage.style.position = 'relative';
            
            beforeImage.style.display = 'none';
            afterImage.style.display = 'block';
            afterImage.style.clipPath = 'inset(0 0% 0 0)';
            document.getElementById('sliderLine').classList.remove('active');
            
            currentView = 'after';
        }}

        function showInstructions() {{
            document.getElementById('initial-view').classList.add('hidden');
            document.getElementById('instructions-view').classList.remove('hidden');
        }}

        function backToInitial() {{
            document.getElementById('instructions-view').classList.add('hidden');
            document.getElementById('tryon-view').classList.add('hidden');
            document.getElementById('initial-view').classList.remove('hidden');
            
            uploadedImageData = null;
            afterImageData = null;
            document.getElementById('toggleButtons').classList.add('hidden');
            currentView = 'before';
        }}

        function triggerUpload() {{
            document.getElementById('photoUpload').click();
        }}

        async function handleUpload(event) {{
            const file = event.target.files[0];
            if (!file) return;
            
            console.log('File selected:', file.name, file.type, file.size);
            
            try {{
                await processImageDirectly(file);
            }} catch (error) {{
                console.error('Upload error:', error);
                alert('Failed to process image. Please try again.');
            }}
        }}

        // Process image with multiple auth attempts
                async function processImageDirectly(file) {{
            try {{
                console.log('Processing image directly via API...');
                console.log('Using API Key:', API_KEY);
                
                // Try multiple authentication methods
                const authMethods = [
                    // Method 1: Query parameter (primary - should work if authenticated)
                    {{
                        name: 'Query parameter',
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', file);
                            fd.append('org_id', '1');
                            fd.append('category', CATEGORY);
                            return fd;
                        }},
                        url: `/api/vto/upload?api_key=${{encodeURIComponent(API_KEY)}}`
                    }},
                    // Method 2: X-API-Key header (secondary - should work if authenticated)
                    {{
                        name: 'X-API-Key header',
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', file);
                            fd.append('org_id', '1');
                            fd.append('category', CATEGORY);
                            return fd;
                        }},
                        url: '/api/vto/upload',
                        headers: {{ 'X-API-Key': API_KEY }}
                    }},
                    // Method 3: Bearer token (fallback - may not be supported)
                    {{
                        name: 'Bearer token',
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', file);
                            fd.append('org_id', '1');
                            fd.append('category', CATEGORY);
                            return fd;
                        }},
                        url: '/api/vto/upload',
                        headers: {{ 'Authorization': `Bearer ${{API_KEY}}` }}
                    }},
                    // Method 4: API key in form data (fallback - may not be supported)
                    {{
                        name: 'Form data',
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
                let lastError;
                let lastStatusCode;
                let serviceUnavailableError = null;
                let authenticationError = null;

                for (const method of authMethods) {{
                    try {{
                        console.log(`Trying authentication method: ${{method.name}}`);
                        
                        const options = {{
                            method: 'POST',
                            body: method.getFormData()
                        }};
                        
                        if (method.headers) {{
                            options.headers = method.headers;
                        }}

                        response = await fetch(method.url, options);
                        lastStatusCode = response.status;
                        
                        console.log(`Method ${{method.name}} response status:`, response.status);
                        
                        if (response.ok) {{
                            console.log(`✅ Success with method: ${{method.name}}`);
                            break;
                        }}
                        
                        const errorText = await response.text();
                        lastError = `${{method.name}}: HTTP ${{response.status}} - ${{errorText}}`;
                        console.warn(lastError);
                        
                        // Check if this is a service unavailable error (503)
                        if (response.status === 503) {{
                            let errorDetail = 'Service temporarily unavailable';
                            try {{
                                const errorData = JSON.parse(errorText);
                                if (errorData.detail) {{
                                    errorDetail = errorData.detail;
                                }}
                            }} catch (e) {{
                                // If we can't parse JSON, use the text as is
                                if (errorText.includes('not reachable') || errorText.includes('unavailable')) {{
                                    errorDetail = errorText;
                                }}
                            }}
                            serviceUnavailableError = new Error(errorDetail);
                        }}
                        
                        // Check if this is a REAL authentication error (401/403 on primary methods)
                        if ((response.status === 401 || response.status === 403) && 
                            (method.name === 'Query parameter' || method.name === 'X-API-Key header')) {{
                            let authErrorDetail = 'Authentication failed';
                            try {{
                                const errorData = JSON.parse(errorText);
                                if (errorData.detail) {{
                                    authErrorDetail = errorData.detail;
                                }}
                            }} catch (e) {{
                                authErrorDetail = errorText || 'Invalid API key or credentials';
                            }}
                            authenticationError = new Error(authErrorDetail);
                        }}
                        
                    }} catch (err) {{
                        lastError = `${{method.name}}: ${{err.message}}`;
                        console.warn(lastError);
                        
                        // Check for network errors that indicate service issues
                        if (err.message.includes('Failed to fetch') || 
                            err.message.includes('NetworkError') ||
                            err.message.includes('ECONNREFUSED')) {{
                            serviceUnavailableError = new Error('Unable to connect to the server. Please check your internet connection and try again.');
                        }}
                        continue;
                    }}
                }}

                if (!response) {{
                    throw new Error('Unable to connect to the server. Please check your internet connection and try again.');
                }}

                if (!response.ok) {{
                    // Priority 1: If we encountered service unavailable errors during any attempt
                    if (serviceUnavailableError) {{
                        throw serviceUnavailableError;
                    }}
                    
                    // Priority 2: If we have a REAL authentication error from primary methods
                    if (authenticationError) {{
                        throw authenticationError;
                    }}
                    
                    // Priority 3: Check the final status code for other errors
                    if (lastStatusCode === 401 || lastStatusCode === 403) {{
                        // This might be from fallback methods, but if all methods failed with auth errors, it's likely real
                        let authErrorDetail = 'Authentication failed';
                        try {{
                            const errorData = await response.json();
                            if (errorData.detail) {{
                                authErrorDetail = errorData.detail;
                            }}
                        }} catch (e) {{
                            authErrorDetail = await response.text() || 'Invalid API key or credentials';
                        }}
                        throw new Error(authErrorDetail);
                    }} else if (lastStatusCode === 500 || lastStatusCode === 503) {{
                        let errorDetail = 'Service temporarily unavailable';
                        try {{
                            const errorData = await response.json();
                            if (errorData.detail) {{
                                errorDetail = errorData.detail;
                            }}
                        }} catch (e) {{
                            errorDetail = await response.text() || 'Internal server error';
                        }}
                        throw new Error(errorDetail);
                    }} else if (lastStatusCode === 429) {{
                        throw new Error('Usage limit reached. Please try again later or upgrade your subscription.');
                    }} else {{
                        throw new Error(`Request failed with status ${{lastStatusCode}}. Please try again.`);
                    }}
                }}

                const result = await response.json();
                console.log('API response received:', result);
                
                const processedImage = result.processed_image || result.image || result.data;
                
                if (!processedImage) {{
                    throw new Error('No processed image found in API response');
                }}

                // Ensure base64 string has proper format
                let formattedImage = processedImage;
                if (!formattedImage.startsWith('data:image')) {{
                    formattedImage = `data:image/jpeg;base64,${{formattedImage}}`;
                }}

                uploadedImageData = formattedImage;
                const beforeImage = document.getElementById('beforeImage');
                const afterImage = document.getElementById('afterImage');
                
                beforeImage.src = uploadedImageData;
                afterImage.src = uploadedImageData;
                
                beforeImage.style.position = 'relative';
                afterImage.style.position = 'relative';
                
                document.getElementById('instructions-view').classList.add('hidden');
                document.getElementById('tryon-view').classList.remove('hidden');
                
                showBefore();
                
                console.log('✅ Image processed and displayed successfully');
                
            }} catch (error) {{
                console.error('❌ Direct processing error:', error);
                
                // Provide more user-friendly error messages
                let userMessage = error.message;
                
                if (error.message.includes('Virtual try-on service is not reachable') ||
                    error.message.includes('Service temporarily unavailable') ||
                    error.message.includes('not reachable') ||
                    error.message.includes('connection') ||
                    error.message.includes('unavailable')) {{
                    userMessage = 'Our virtual try-on service is temporarily unavailable. Please try again in a few minutes.';
                }} else if (error.message.includes('Authentication failed') ||
                           error.message.includes('Invalid API key') ||
                           error.message.includes('API key required')) {{
                    userMessage = 'Authentication failed. Please check your API key and try again.';
                }} else if (error.message.includes('Failed to fetch') ||
                           error.message.includes('NetworkError') ||
                           error.message.includes('Unable to connect')) {{
                    userMessage = 'Unable to connect to the server. Please check your internet connection and try again.';
                }}
                
                alert('Failed to process image: ' + userMessage);
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
                
                const byteArray = new Uint8Array(byteNumbers);
                byteArrays.push(byteArray);
            }}
            
            return new Blob(byteArrays, {{ type: 'image/jpeg' }});
        }}

        async function handleApplyMakeup() {{
            if (!uploadedImageData || isProcessing) return;
            
            isProcessing = true;
            const applyBtn = document.getElementById('apply-makeup-btn');
            applyBtn.disabled = true;
            applyBtn.textContent = 'Applying...';
            
            try {{
                const blob = base64ToBlob(uploadedImageData);
                
                // Try multiple auth methods for makeup application too
                const authMethods = [
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', blob, 'processed-image.jpg');
                            fd.append('color', '{color}');
                            fd.append('product_name', '{product_name}');
                            return fd;
                        }},
                        url: `/api/vto/apply_{category}?api_key=${{encodeURIComponent(API_KEY)}}`
                    }},
                    {{
                        getFormData: () => {{
                            const fd = new FormData();
                            fd.append('image', blob, 'processed-image.jpg');
                            fd.append('color', '{color}');
                            fd.append('product_name', '{product_name}');
                            fd.append('api_key', API_KEY);
                            return fd;
                        }},
                        url: '/api/vto/apply_{category}'
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
                    const errorText = await response.text();
                    throw new Error(`Failed to apply makeup: ${{errorText}}`);
                }}

                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('image/')) {{
                    const imageBlob = await response.blob();
                    const imageUrl = URL.createObjectURL(imageBlob);
                    afterImageData = imageUrl;
                    
                    const afterImage = document.getElementById('afterImage');
                    afterImage.src = imageUrl;
                    
                    afterImage.onload = function() {{
                        showComparison();
                        document.getElementById('toggleButtons').classList.remove('hidden');
                        applyBtn.textContent = 'Makeup Applied!';
                        applyBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                        
                        setTimeout(() => {{
                            applyBtn.textContent = 'Reapply Makeup';
                            applyBtn.style.background = 'linear-gradient(135deg, #e879f9, #c084fc)';
                        }}, 2000);
                    }};
                }} else {{
                    const errorText = await response.text();
                    throw new Error(errorText);
                }}
                
            }} catch (error) {{
                console.error('Makeup application error:', error);
                alert('Failed to apply makeup: ' + error.message);
                applyBtn.textContent = 'Apply Makeup';
            }} finally {{
                isProcessing = false;
                applyBtn.disabled = false;
            }}
        }}

        function startSelfieMode() {{
            alert('Selfie mode would be implemented here');
        }}

        function useModel() {{
            alert('Model selection would be implemented here');
        }}

        function closeVTO() {{
            window.parent.postMessage({{ action: 'close' }}, '*');
        }}
    </script>
</body>
</html>
    """
    return HTMLResponse(content=interface_html)