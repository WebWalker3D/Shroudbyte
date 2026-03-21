"""Fingerprint resistance via JavaScript injection.

Overrides browser APIs commonly used for fingerprinting to return
slightly randomized or generic values, making it harder for sites
to build a unique fingerprint of the user.
"""


def get_fingerprint_resistance_js() -> str:
    """Return JS to inject into pages for fingerprint resistance."""
    return """
(function() {
    'use strict';
    if (window.__shroudFingerprintResistance) return;
    window.__shroudFingerprintResistance = true;

    // --- Seed a simple PRNG per page load (consistent within a page) ---
    var seed = Math.floor(Math.random() * 2147483647);
    function prng() {
        seed = (seed * 16807) % 2147483647;
        return (seed - 1) / 2147483646;
    }

    // --- Canvas fingerprint resistance ---
    // Add subtle noise to canvas toDataURL / toBlob output
    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {
        try {
            var ctx = this.getContext('2d');
            if (ctx) {
                var imageData = ctx.getImageData(0, 0, this.width, this.height);
                var data = imageData.data;
                // Add subtle noise to a few random pixels
                for (var i = 0; i < Math.min(10, data.length / 4); i++) {
                    var idx = Math.floor(prng() * (data.length / 4)) * 4;
                    data[idx] = (data[idx] + Math.floor(prng() * 3) - 1) & 0xFF;
                }
                ctx.putImageData(imageData, 0, 0);
            }
        } catch(e) {}
        return origToDataURL.apply(this, arguments);
    };

    var origToBlob = HTMLCanvasElement.prototype.toBlob;
    if (origToBlob) {
        HTMLCanvasElement.prototype.toBlob = function(callback) {
            try {
                var ctx = this.getContext('2d');
                if (ctx) {
                    var imageData = ctx.getImageData(0, 0, this.width, this.height);
                    var data = imageData.data;
                    for (var i = 0; i < Math.min(10, data.length / 4); i++) {
                        var idx = Math.floor(prng() * (data.length / 4)) * 4;
                        data[idx] = (data[idx] + Math.floor(prng() * 3) - 1) & 0xFF;
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
            } catch(e) {}
            return origToBlob.apply(this, arguments);
        };
    }

    // --- WebGL fingerprint resistance ---
    var origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        // RENDERER (0x1F01) and VENDOR (0x1F00)
        if (param === 0x1F01) return 'WebKit WebGL';
        if (param === 0x1F00) return 'WebKit';
        // UNMASKED_RENDERER_WEBGL and UNMASKED_VENDOR_WEBGL
        var ext = this.getExtension('WEBGL_debug_renderer_info');
        if (ext) {
            if (param === ext.UNMASKED_RENDERER_WEBGL) return 'ANGLE (Generic GPU)';
            if (param === ext.UNMASKED_VENDOR_WEBGL) return 'Google Inc.';
        }
        return origGetParam.apply(this, arguments);
    };

    // Same for WebGL2
    if (typeof WebGL2RenderingContext !== 'undefined') {
        var origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {
            if (param === 0x1F01) return 'WebKit WebGL';
            if (param === 0x1F00) return 'WebKit';
            var ext = this.getExtension('WEBGL_debug_renderer_info');
            if (ext) {
                if (param === ext.UNMASKED_RENDERER_WEBGL) return 'ANGLE (Generic GPU)';
                if (param === ext.UNMASKED_VENDOR_WEBGL) return 'Google Inc.';
            }
            return origGetParam2.apply(this, arguments);
        };
    }

    // --- AudioContext fingerprint resistance ---
    if (typeof AudioContext !== 'undefined') {
        var origCreateOscillator = AudioContext.prototype.createOscillator;
        AudioContext.prototype.createOscillator = function() {
            var osc = origCreateOscillator.apply(this, arguments);
            // Slightly detune to alter audio fingerprint
            var origFreqGet = Object.getOwnPropertyDescriptor(
                OscillatorNode.prototype, 'frequency'
            );
            if (osc.frequency && osc.frequency.value !== undefined) {
                osc.frequency.value += (prng() - 0.5) * 0.001;
            }
            return osc;
        };

        var origGetFloat = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(array) {
            origGetFloat.apply(this, arguments);
            // Add tiny noise to frequency data
            for (var i = 0; i < array.length; i++) {
                array[i] += (prng() - 0.5) * 0.1;
            }
        };
    }

    // --- Hardware / navigator spoofing ---
    try {
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: function() { return 4; },
            configurable: true
        });
    } catch(e) {}

    try {
        Object.defineProperty(navigator, 'deviceMemory', {
            get: function() { return 8; },
            configurable: true
        });
    } catch(e) {}

    // --- Screen resolution rounding ---
    try {
        var realWidth = screen.width;
        var realHeight = screen.height;
        // Round to nearest common resolution
        var commonWidths = [1366, 1440, 1536, 1600, 1920, 2560];
        var closest = commonWidths.reduce(function(prev, curr) {
            return Math.abs(curr - realWidth) < Math.abs(prev - realWidth) ? curr : prev;
        });
        Object.defineProperty(screen, 'width', {
            get: function() { return closest; },
            configurable: true
        });
        var ratio = closest / realWidth;
        Object.defineProperty(screen, 'height', {
            get: function() { return Math.round(realHeight * ratio); },
            configurable: true
        });
        Object.defineProperty(screen, 'availWidth', {
            get: function() { return closest; },
            configurable: true
        });
        Object.defineProperty(screen, 'availHeight', {
            get: function() { return Math.round(realHeight * ratio); },
            configurable: true
        });
    } catch(e) {}

    // --- Date timezone spoofing (report UTC offset as 0 to avoid timezone leaks) ---
    // Disabled by default as it can break sites. Uncomment to enable:
    // var origGetTimezone = Date.prototype.getTimezoneOffset;
    // Date.prototype.getTimezoneOffset = function() { return 0; };

})();
"""
