// Web Audio API Dispatch Alert Synthesizer for CAD Command Center

class AudioAlertSystem {
    constructor() {
        this.ctx = null;
        this.enabled = true;
    }

    init() {
        if (!this.ctx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                this.ctx = new AudioCtx();
            }
        }
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume().catch(() => {});
        }
        return this.ctx;
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }

    playTone(frequency = 880, durationMs = 120, type = 'sine', volume = 0.08) {
        if (!this.enabled) return;
        try {
            const audioCtx = this.init();
            if (!audioCtx) return;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(frequency, audioCtx.currentTime);
            gain.gain.setValueAtTime(volume, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + durationMs / 1000);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + durationMs / 1000);
        } catch (e) {
            // Suppress browser autoplay policy errors or muted audio
        }
    }

    playBeep(frequency = 880, durationMs = 120) {
        this.playTone(frequency, durationMs, 'sine', 0.08);
    }

    playAlert() {
        this.playTone(520, 240, 'triangle', 0.12);
    }

    playSuccess() {
        this.playTone(1200, 100, 'sine', 0.08);
    }

    playCriticalAlert() {
        if (!this.enabled) return;
        try {
            const ctx = this.init();
            if (!ctx) return;
            const osc1 = ctx.createOscillator();
            const osc2 = ctx.createOscillator();
            const gain = ctx.createGain();

            osc1.type = 'sawtooth';
            osc2.type = 'sine';

            osc1.frequency.setValueAtTime(880, ctx.currentTime); // A5
            osc1.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.35);

            osc2.frequency.setValueAtTime(440, ctx.currentTime);
            osc2.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.35);

            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);

            osc1.connect(gain);
            osc2.connect(gain);
            gain.connect(ctx.destination);

            osc1.start();
            osc2.start();
            osc1.stop(ctx.currentTime + 0.35);
            osc2.stop(ctx.currentTime + 0.35);
        } catch (e) {
            console.warn("Audio playback error:", e);
        }
    }

    playDispatchPing() {
        if (!this.enabled) return;
        try {
            const ctx = this.init();
            if (!ctx) return;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1); // A5

            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start();
            osc.stop(ctx.currentTime + 0.25);
        } catch (e) {
            console.warn("Audio playback error:", e);
        }
    }

    playSiren() {
        if (!this.enabled) return;
        try {
            const ctx = this.init();
            if (!ctx) return;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.linearRampToValueAtTime(900, ctx.currentTime + 0.3);
            osc.frequency.linearRampToValueAtTime(600, ctx.currentTime + 0.6);

            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start();
            osc.stop(ctx.currentTime + 0.6);
        } catch (e) {
            console.warn("Audio playback error:", e);
        }
    }
}

// Global instance with full method safety
window.cadAudio = new AudioAlertSystem();

