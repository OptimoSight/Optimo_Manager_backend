// Virtual Try-On Widget JavaScript with Smart Network Detection
(function () {
    'use strict';

    // // List of possible URLs for dynamic selection
    // const possibleUrls = [
    //     'https://192.168.50.148:42413',
    //     'https://192.168.0.111:42413',
    //     'https://localhost:42413'
    // ];

    // Dynamic base URL detection with reachability check
    async function getBaseUrl() {
        const hostname = window.location.hostname;

        // ✅ Force production base URL when running on GitHub Pages
        if (hostname.includes("github.io")) {
            console.log("Running on GitHub Pages – forcing backend base URL");
            return "https://optimo-manager-backend.onrender.com";
        }

        // ✅ Local network detection and reachability test
        const possibleUrls = [
            "https://192.168.50.148:42413",
            "https://192.168.0.111:42413",
            "https://localhost:42413",
            "https://optimosight.github.io",
            "https://optimo-manager-backend.onrender.com"
        ];

        const timeout = 2000; // 2 seconds timeout per request

        async function testUrl(url) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);
                const response = await fetch(`${url}/api/vto/upload`, {
                    method: "HEAD",
                    signal: controller.signal,
                    headers: { "X-API-Key": "OptimosightGuest999" }
                });
                clearTimeout(timeoutId);
                return response.ok;
            } catch {
                return false;
            }
        }

        for (const url of possibleUrls) {
            if (await testUrl(url)) return url;
        }

        console.error("No URLs were reachable, falling back to:", possibleUrls[0]);
        return possibleUrls[0];
    }


    // Configuration
    let CONFIG = {
        baseUrl: null, // Temporary null until resolved
        retryAttempts: 3,
        retryDelay: 1000,
        iframeTimeout: 15000,
        validCategories: ['lipstick', 'eyeshadow', 'blush', 'foundation', 'mascara', 'eyeliner']
    };

    // Initialize baseUrl asynchronously
    async function initializeConfig() {
        try {
            CONFIG.baseUrl = await getBaseUrl();
            console.log('VTO Widget initialized with base URL:', CONFIG.baseUrl);
            console.log('Current hostname:', window.location.hostname);
        } catch (error) {
            console.error('Failed to initialize base URL:', error);
            CONFIG.baseUrl = possibleUrls[0]; // Use the first URL as fallback
            console.log('Using fallback URL:', CONFIG.baseUrl);
        }
    }

    // Image Processor using API
    class ImageProcessor {
        async processImage(file, category = 'lipstick', orgId = '1') {
            try {
                console.log('Starting image processing via API...');
                console.log('API Base URL:', CONFIG.baseUrl);

                const formData = new FormData();
                formData.append('image', file);
                formData.append('org_id', orgId);
                formData.append('category', category);

                // Try different authentication methods
                const authMethods = [
                    {
                        name: 'X-API-Key header',
                        url: `${CONFIG.baseUrl}/api/vto/upload`,
                        options: {
                            method: 'POST',
                            headers: { 'X-API-Key': 'OptimosightGuest999' },
                            body: formData
                        }
                    },
                    {
                        name: 'Query parameter',
                        url: `${CONFIG.baseUrl}/api/vto/upload?api_key=${encodeURIComponent('OptimosightGuest999')}`,
                        options: { method: 'POST', body: formData }
                    },
                    {
                        name: 'Bearer token',
                        url: `${CONFIG.baseUrl}/api/vto/upload`,
                        options: {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer OptimosightGuest999` },
                            body: formData
                        }
                    }
                ];

                let response;
                let lastError;

                for (const method of authMethods) {
                    try {
                        console.log(`Trying authentication method: ${method.name}`);
                        response = await fetch(method.url, method.options);
                        if (response.ok) {
                            console.log(`Success with method: ${method.name}`);
                            break;
                        }
                        const errorText = await response.text();
                        lastError = `HTTP ${response.status}: ${errorText}`;
                        console.warn(`Method ${method.name} failed:`, lastError);
                    } catch (err) {
                        lastError = err.message;
                        console.warn(`Method ${method.name} error:`, err);
                        continue;
                    }
                }

                // Fallback: include API key in form data
                if (!response || !response.ok) {
                    console.log('Trying fallback method with API key in form data');
                    const formDataWithKey = new FormData();
                    formDataWithKey.append('image', file);
                    formDataWithKey.append('org_id', orgId);
                    formDataWithKey.append('category', category);
                    formDataWithKey.append('api_key', 'OptimosightGuest999');

                    response = await fetch(`${CONFIG.baseUrl}/api/vto/upload`, {
                        method: 'POST',
                        body: formDataWithKey
                    });
                }

                if (!response.ok) {
                    const errorText = await response.text();
                    let errorMessage;
                    try {
                        const errorJson = JSON.parse(errorText);
                        errorMessage = errorJson.detail || errorJson.message || 'Failed to process image';
                    } catch {
                        errorMessage = errorText || `HTTP Error: ${response.status}`;
                    }
                    throw new Error(errorMessage);
                }

                const result = await response.json();

                // Handle different response formats
                const processedImage = result.processed_image || result.image || result.data;

                if (!processedImage) {
                    console.log('API Response:', result);
                    throw new Error('No processed image found in API response');
                }

                // Ensure base64 string has proper format
                let formattedImage = processedImage;
                if (!formattedImage.startsWith('data:image')) {
                    formattedImage = `data:image/jpeg;base64,${formattedImage}`;
                }

                console.log('Image processed successfully via API');

                return {
                    processed: formattedImage,
                    crop: result.crop_region || { x: 0, y: 0, w: 0, h: 0 }
                };
            } catch (error) {
                console.error('API image processing error:', error);
                throw error;
            }
        }

        // Helper function to convert base64 to blob
        base64ToBlob(base64Data) {
            const base64WithoutPrefix = base64Data.split(',')[1] || base64Data;
            const byteCharacters = atob(base64WithoutPrefix);
            const byteArrays = [];

            for (let offset = 0; offset < byteCharacters.length; offset += 512) {
                const slice = byteCharacters.slice(offset, offset + 512);
                const byteNumbers = new Array(slice.length);

                for (let i = 0; i < slice.length; i++) {
                    byteNumbers[i] = slice.charCodeAt(i);
                }

                const byteArray = new Uint8Array(byteNumbers);
                byteArrays.push(byteArray);
            }

            return new Blob(byteArrays, { type: 'image/jpeg' });
        }
    }

    // Main VTO Widget Class
    class VTOWidget {
        constructor() {
            this.modal = null;
            this.iframe = null;
            this.loading = null;
            this.currentRetry = 0;
            this.iframeLoaded = false;
            this.currentConfig = null;
            this.imageProcessor = new ImageProcessor();
            this.init();
        }

        init() {
            this.createModal();
            this.bindEvents();
            this.initializeButtons();
        }

        createModal() {
            if (document.getElementById('vtoModal')) return;

            const modalHTML = `
                <div id="vtoModal" class="vto-modal">
                    <div class="vto-modal-content">
                        <span class="vto-close" onclick="VTOWidget.close()">&times;</span>
                        <div class="vto-loading" id="vtoLoading">
                            <div class="vto-spinner"></div>
                            <div>Loading Virtual Try-On...</div>
                        </div>
                        <iframe id="vtoIframe" class="vto-iframe" style="display: none;" allow="camera; microphone"></iframe>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHTML);

            this.modal = document.getElementById('vtoModal');
            this.iframe = document.getElementById('vtoIframe');
            this.loading = document.getElementById('vtoLoading');
        }

        bindEvents() {
            if (this.modal) {
                this.modal.addEventListener('click', (e) => {
                    if (e.target === this.modal) {
                        this.close();
                    }
                });
            }

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.modal && this.modal.classList.contains('active')) {
                    this.close();
                }
            });

            if (this.iframe) {
                this.iframe.addEventListener('load', () => {
                    this.onIframeLoad();
                });

                this.iframe.addEventListener('error', () => {
                    this.onIframeError();
                });
            }

            window.addEventListener('message', (e) => {
                this.handleIframeMessage(e);
            });
        }

        async handleIframeMessage(event) {
            // Accept messages from both backend and frontend origins
            const allowedOrigins = [
                'https://192.168.50.148:42413',
                'https://192.168.0.111:42413',
                'https://localhost:42413',
                'https://192.168.50.148:42414',
                'https://192.168.0.111:42414',
                'https://localhost:42414',
                'https://optimosight.github.io',
                'https://optimo-manager-backend.onrender.com',
                CONFIG.baseUrl,
                window.location.origin
            ];

            // More lenient origin check for development
            const isAllowedOrigin = allowedOrigins.some(origin =>
                event.origin === origin ||
                event.origin.includes('192.168.0.111') ||
                event.origin.includes('192.168.50.148') ||
                event.origin.includes('optimosight.github.io') ||
                event.origin.includes('optimo-manager-backend.onrender.com') ||
                event.origin.includes('localhost')
            );

            if (!isAllowedOrigin) {
                console.warn('Rejected message from unauthorized origin:', event.origin);
                return;
            }

            console.log('Received message:', event.data, 'from:', event.origin);

            if (event.data.action === 'close') {
                this.close();
            } else if (event.data.action === 'processImage') {
                await this.handleImageProcessing(event.data.file, event.data.category);
            } else if (event.data.action === 'uploadFile') {
                // Handle file upload from iframe
                await this.handleFileUpload(event.data);
            }
        }

        async handleFileUpload(data) {
            try {
                console.log('Handling file upload from iframe');

                // Convert base64 to File object
                const response = await fetch(data.fileData);
                const blob = await response.blob();
                const file = new File([blob], data.fileName || 'upload.jpg', {
                    type: data.fileType || 'image/jpeg'
                });

                // Process the image
                const processed = await this.imageProcessor.processImage(
                    file,
                    data.category || 'lipstick'
                );

                // Send processed image back to iframe
                this.iframe.contentWindow.postMessage({
                    action: 'imageProcessed',
                    data: processed.processed,
                    crop: processed.crop
                }, '*'); // Use wildcard for development

                console.log('Image processed and sent back to iframe');

            } catch (error) {
                console.error('File upload error:', error);
                this.iframe.contentWindow.postMessage({
                    action: 'processingError',
                    error: error.message || 'Failed to process image'
                }, '*');
            }
        }

        async handleImageProcessing(fileData, category = 'lipstick') {
            try {
                this.showLoadingMessage('Processing image via API...');

                // Convert base64 to blob
                const response = await fetch(fileData);
                const blob = await response.blob();
                const file = new File([blob], 'upload.jpg', { type: 'image/jpeg' });

                // Process image via API
                const processed = await this.imageProcessor.processImage(file, category);

                // Send processed image back to iframe - use wildcard origin for development
                this.iframe.contentWindow.postMessage({
                    action: 'imageProcessed',
                    data: processed.processed,
                    crop: processed.crop
                }, '*'); // Changed from CONFIG.baseUrl to '*'

                console.log('Image processed and sent to iframe');

            } catch (error) {
                console.error('Image processing error:', error);
                this.iframe.contentWindow.postMessage({
                    action: 'processingError',
                    error: error.message || 'Failed to process image via API'
                }, '*'); // Changed from CONFIG.baseUrl to '*'
            }
        }

        showLoadingMessage(message) {
            if (this.loading) {
                const loadingText = this.loading.querySelector('div:last-child');
                if (loadingText) {
                    loadingText.textContent = message;
                }
            }
        }

        initializeButtons() {
            const buttons = document.querySelectorAll('.vto-try-now-btn');
            console.log(`Initializing ${buttons.length} VTO buttons`);
            buttons.forEach(button => {
                if (!button.dataset.vtoInitialized) {
                    button.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.handleButtonClick(button);
                    });
                    button.dataset.vtoInitialized = 'true';
                }
            });
        }

        handleButtonClick(button) {
            const config = {
                category: button.dataset.category || 'lipstick',
                color: button.dataset.color || '#e91e63',
                colorName: button.dataset.colorName || 'Default',
                productName: button.dataset.productName || 'Product',
                apiKey: button.dataset.apiKey,
                mode: button.dataset.mode || 'both',
                colors: button.dataset.colors || button.dataset.color || '#e91e63',
                colorNames: button.dataset.colorNames || button.dataset.colorName || 'Default'
            };

            console.log('VTO Button clicked with config:', config);

            if (!CONFIG.validCategories.includes(config.category)) {
                this.showError('Invalid makeup category');
                return;
            }

            if (!config.apiKey) {
                this.showError('Configuration error: API key missing');
                return;
            }

            this.open(config);
        }

        open(config) {
            this.currentConfig = config;
            this.currentRetry = 0;
            this.iframeLoaded = false;

            if (this.modal) {
                this.modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }

            this.loadIframe(config);

            setTimeout(() => {
                if (!this.iframeLoaded && this.loading) {
                    console.error('Iframe loading timeout');
                    this.showError('Loading timeout. Please check your connection and try again.');
                }
            }, CONFIG.iframeTimeout);
        }

        loadIframe(config) {
            if (!this.iframe || !this.loading) return;

            this.loading.style.display = 'block';
            this.iframe.style.display = 'none';

            const params = new URLSearchParams({
                api_key: config.apiKey,
                color: config.color,
                product_name: config.productName,
                color_name: config.colorName,
                mode: config.mode,
                category: config.category,
                colors: config.colors,
                color_names: config.colorNames,
                parent_origin: window.location.origin // Add parent origin
            });

            const iframeUrl = `${CONFIG.baseUrl}/widget/vto-interface?${params.toString()}`;
            console.log('Loading iframe URL:', iframeUrl);
            this.iframe.src = iframeUrl;
        }

        onIframeLoad() {
            console.log('Iframe loaded successfully');
            this.iframeLoaded = true;

            if (this.loading && this.iframe) {
                this.loading.style.display = 'none';
                this.iframe.style.display = 'block';
            }
        }

        onIframeError() {
            console.error('Iframe failed to load');
            this.retryLoad();
        }

        retryLoad() {
            if (this.currentRetry < CONFIG.retryAttempts && this.currentConfig) {
                this.currentRetry++;
                console.log(`Retrying iframe load (${this.currentRetry}/${CONFIG.retryAttempts})`);

                if (this.loading) {
                    const loadingText = this.loading.querySelector('div:last-child');
                    if (loadingText) {
                        loadingText.textContent = `Retrying... (${this.currentRetry}/${CONFIG.retryAttempts})`;
                    }
                }

                setTimeout(() => {
                    this.loadIframe(this.currentConfig);
                }, CONFIG.retryDelay);
            } else {
                console.error('Max retry attempts reached');
                this.showError('Failed to load Virtual Try-On. Please check your connection.');
            }
        }

        showError(message) {
            if (!this.modal) return;

            console.error('VTO Error:', message);

            const errorHTML = `
                <div class="vto-error">
                    <div class="vto-error-icon">⚠️</div>
                    <div class="vto-error-title">Oops! Something went wrong</div>
                    <div class="vto-error-message">${message}</div>
                    <button class="vto-retry-btn" onclick="VTOWidget.retry()">Try Again</button>
                </div>
            `;

            if (this.loading) this.loading.style.display = 'none';
            if (this.iframe) this.iframe.style.display = 'none';

            const modalContent = this.modal.querySelector('.vto-modal-content');
            if (modalContent) {
                const existingError = modalContent.querySelector('.vto-error');
                if (existingError) existingError.remove();
                modalContent.insertAdjacentHTML('beforeend', errorHTML);
            }
        }

        retry() {
            const error = this.modal?.querySelector('.vto-error');
            if (error) error.remove();
            this.currentRetry = 0;
            if (this.currentConfig) {
                this.loadIframe(this.currentConfig);
            }
        }

        close() {
            if (this.modal) {
                this.modal.classList.remove('active');
                document.body.style.overflow = '';
                if (this.iframe) this.iframe.src = 'about:blank';
                this.iframeLoaded = false;
                this.currentRetry = 0;
                this.currentConfig = null;
                const error = this.modal.querySelector('.vto-error');
                if (error) error.remove();
                if (this.loading) {
                    this.loading.style.display = 'block';
                    const loadingText = this.loading.querySelector('div:last-child');
                    if (loadingText) loadingText.textContent = 'Loading Virtual Try-On...';
                }
            }
        }

        static open(config) {
            if (!window.vtoWidgetInstance) {
                window.vtoWidgetInstance = new VTOWidget();
            }
            window.vtoWidgetInstance.open(config);
        }

        static close() {
            if (window.vtoWidgetInstance) {
                window.vtoWidgetInstance.close();
            }
        }

        static retry() {
            if (window.vtoWidgetInstance) {
                window.vtoWidgetInstance.retry();
            }
        }

        static refresh() {
            if (window.vtoWidgetInstance) {
                window.vtoWidgetInstance.initializeButtons();
            }
        }
    }

    function initialize() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                window.vtoWidgetInstance = new VTOWidget();
                console.log('VTO Widget initialized on DOMContentLoaded');
            });
        } else {
            window.vtoWidgetInstance = new VTOWidget();
            console.log('VTO Widget initialized immediately');
        }
    }

    // Initialize CONFIG and widget
    initializeConfig().then(() => {
        window.VTOWidget = VTOWidget;
        initialize();
    }).catch(error => {
        console.error('Failed to initialize base URL:', error);
        CONFIG.baseUrl = possibleUrls[0]; // Use the first URL as fallback
        console.log('Using fallback URL:', CONFIG.baseUrl);
        window.VTOWidget = VTOWidget;
        initialize();
    });

    if (window.MutationObserver) {
        const observer = new MutationObserver((mutations) => {
            let shouldRefresh = false;
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) {
                        if (node.classList?.contains('vto-try-now-btn') ||
                            node.querySelector?.('.vto-try-now-btn')) {
                            shouldRefresh = true;
                        }
                    }
                });
            });
            if (shouldRefresh && window.vtoWidgetInstance) {
                clearTimeout(window.vtoRefreshTimeout);
                window.vtoRefreshTimeout = setTimeout(() => {
                    console.log('Refreshing VTO buttons after DOM mutation');
                    window.vtoWidgetInstance.initializeButtons();
                }, 100);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    window.addEventListener('beforeunload', () => {
        if (window.vtoWidgetInstance) {
            window.vtoWidgetInstance.close();
        }
    });

})();

if (typeof jQuery !== 'undefined') {
    jQuery.fn.vtoWidget = function (options = {}) {
        return this.each(function () {
            const $this = jQuery(this);
            if (options.category) $this.attr('data-category', options.category);
            if (options.color) $this.attr('data-color', options.color);
            if (options.colorName) $this.attr('data-color-name', options.colorName);
            if (options.productName) $this.attr('data-product-name', options.productName);
            if (options.apiKey) $this.attr('data-api-key', options.apiKey);
            if (options.mode) $this.attr('data-mode', options.mode);
            if (options.colors) $this.attr('data-colors', options.colors);
            if (options.colorNames) $this.attr('data-color-names', options.colorNames);
            $this.addClass('vto-try-now-btn');
            if (window.VTOWidget) window.VTOWidget.refresh();
        });
    };
}