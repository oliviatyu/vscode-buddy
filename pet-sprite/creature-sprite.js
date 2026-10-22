/**
 * <creature-sprite> — Composable sprite-sheet state machine Web Component
 *
 * Drop this script anywhere, then use the element like:
 *
 *   <creature-sprite
 *     src="./sprite.png"
 *     state="idle"
 *     frame-width="399"
 *     frame-height="417"
 *     display-width="100"
 *   ></creature-sprite>
 *
 * Or mount programmatically:
 *   const s = CreatureSprite.mount(containerEl, { src, state, displayWidth });
 *
 * API
 * ───
 *   .play(stateName)         — transition to a named state immediately
 *   .states = { … }          — replace the full state definition map
 *   .defineState(name, def)  — add / overwrite a single state
 *   Events:
 *     'statechange'  → detail: { from, to }
 *     'framechange'  → detail: { state, frameIndex, frameId }
 *     'stateend'     → detail: { state }   (oneshot states only)
 *
 * State definition schema:
 * {
 *   frames:  number[]   — sprite frame indices (0-based) to play in order
 *   fps:     number     — playback speed
 *   loop:    boolean    — loop forever if true; play once and stop if false
 *   onEnd:   string?    — state name to auto-transition to when a oneshot ends
 * }
 */

const FRAME_WIDTH_DEFAULT  = 399;
const FRAME_HEIGHT_DEFAULT = 417;
const DISPLAY_WIDTH_DEFAULT = 100;

const DEFAULT_STATES = {
  idle:     { frames: [0, 1, 2, 3], fps: 3,  loop: true  },
  thinking: { frames: [0, 1, 2, 3], fps: 10, loop: true  },
  typing:   { frames: [0, 1, 2, 3], fps: 18, loop: true  },
  alert:    { frames: [0, 1, 2, 3], fps: 10, loop: true  },
  wave:     { frames: [0, 1, 2, 3], fps: 10, loop: false, onEnd: 'idle' },
  processing: { frames: [0, 1, 2, 3], fps: 8, loop: true },
};

class CreatureSprite extends HTMLElement {
  // ── Static factory ───────────────────────────────────────────────────────
  /**
   * Programmatic mount: Creates a <creature-sprite> inside `container`.
   * Props shape: { src, state, displayWidth, frameWidth, frameHeight, states, style }
   * Returns the element instance.
   */
  static mount(container, props = {}) {
    const el = document.createElement('creature-sprite');
    if (props.src)          el.setAttribute('src', props.src);
    if (props.state)        el.setAttribute('state', props.state);
    if (props.displayWidth) el.setAttribute('display-width', String(props.displayWidth));
    if (props.frameWidth)   el.setAttribute('frame-width',   String(props.frameWidth));
    if (props.frameHeight)  el.setAttribute('frame-height',  String(props.frameHeight));
    if (props.style)        Object.assign(el.style, props.style);
    if (props.states)       el._pendingStates = props.states;
    container.appendChild(el);
    return el;
  }

  // ── Lifecycle ────────────────────────────────────────────────────────────
  constructor() {
    super();
    this._stateMap   = { ...DEFAULT_STATES };
    this._current    = null;   // active state name
    this._frameIndex = 0;      // index within current state's frames array
    this._lastTick   = 0;
    this._rafId      = null;
    this._spriteEl   = null;
    this._displayW   = DISPLAY_WIDTH_DEFAULT;
    this._displayH   = Math.round(FRAME_HEIGHT_DEFAULT * DISPLAY_WIDTH_DEFAULT / FRAME_WIDTH_DEFAULT);
    this._pendingStates = null;
  }

  static get observedAttributes() {
    return ['src', 'state', 'display-width', 'frame-width', 'frame-height'];
  }

  connectedCallback() {
    if (this._pendingStates) {
      this._stateMap = this._pendingStates;
      this._pendingStates = null;
    }
    this._build();
    this._startLoop();
    // Honour the `state` attribute on first connect
    const initial = this.getAttribute('state') || 'idle';
    this.play(initial);
  }

  disconnectedCallback() {
    cancelAnimationFrame(this._rafId);
    this._rafId = null;
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal) return;
    if (name === 'state') {
      if (this._spriteEl) this.play(newVal);
    } else {
      // Dimension or src change — rebuild sprite element
      if (this._spriteEl) this._applySprite();
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────
  /** Transition to a named state. Does nothing if state is unknown. */
  play(stateName) {
    if (!this._stateMap[stateName]) {
      console.warn(`[creature-sprite] Unknown state: "${stateName}"`);
      return;
    }
    const from = this._current;
    this._current    = stateName;
    this._frameIndex = 0;
    this._lastTick   = 0;
    this.setAttribute('state', stateName); // keep attribute in sync
    this.dispatchEvent(new CustomEvent('statechange', {
      bubbles: true, detail: { from, to: stateName }
    }));
  }

  /** Replace all state definitions */
  set states(defs) {
    this._stateMap = defs;
  }
  get states() {
    return this._stateMap;
  }

  /** Add or overwrite a single state */
  defineState(name, def) {
    this._stateMap[name] = def;
  }

  // ── Internal ─────────────────────────────────────────────────────────────
  _build() {
    this._computeDimensions();

    if (!this._spriteEl) {
      this._spriteEl = document.createElement('div');
      this._spriteEl.className = 'creature-sprite-inner';
      this.appendChild(this._spriteEl);
    }

    // Host element sizing
    this.style.display = this.style.display || 'inline-block';
    this.style.width   = this._displayW + 'px';
    this.style.height  = this._displayH + 'px';
    this.style.overflow = 'hidden';

    this._applySprite();
  }

  _computeDimensions() {
    const fw = parseInt(this.getAttribute('frame-width')  || FRAME_WIDTH_DEFAULT);
    const fh = parseInt(this.getAttribute('frame-height') || FRAME_HEIGHT_DEFAULT);
    const dw = parseInt(this.getAttribute('display-width')|| DISPLAY_WIDTH_DEFAULT);
    this._displayW  = dw;
    this._displayH  = Math.round(fh * dw / fw);
    this._nativeFrameW = fw;
  }

  _applySprite() {
    this._computeDimensions();
    const src    = this.getAttribute('src') || '';
    const totalW = this._displayW * 4; // 4 frames in sheet

    const s = this._spriteEl.style;
    s.width               = this._displayW + 'px';
    s.height              = this._displayH + 'px';
    s.backgroundImage     = `url('${src}')`;
    s.backgroundRepeat    = 'no-repeat';
    s.backgroundPosition  = '0 0';
    s.backgroundSize      = `${totalW}px ${this._displayH}px`;
    s.imageRendering      = 'pixelated';

    // Also update host size
    this.style.width  = this._displayW + 'px';
    this.style.height = this._displayH + 'px';
  }

  _startLoop() {
    const tick = (ts) => {
      this._rafId = requestAnimationFrame(tick);
      const stateDef = this._stateMap[this._current];
      if (!stateDef || !this._spriteEl) return;

      const interval = 1000 / stateDef.fps;
      if (this._lastTick && ts - this._lastTick < interval) return;
      this._lastTick = ts;

      const { frames, loop, onEnd } = stateDef;
      const frameId = frames[this._frameIndex % frames.length];

      // Move sprite sheet
      this._spriteEl.style.backgroundPositionX = -(frameId * this._displayW) + 'px';

      this.dispatchEvent(new CustomEvent('framechange', {
        bubbles: true,
        detail: { state: this._current, frameIndex: this._frameIndex, frameId }
      }));

      this._frameIndex++;

      // End-of-sequence handling
      if (this._frameIndex >= frames.length) {
        if (loop) {
          this._frameIndex = 0;
        } else {
          // Hold last frame
          this._frameIndex = frames.length - 1;
          this.dispatchEvent(new CustomEvent('stateend', {
            bubbles: true, detail: { state: this._current }
          }));
          if (onEnd) {
            // Give the event a chance to fire before transitioning
            requestAnimationFrame(() => this.play(onEnd));
          }
        }
      }
    };

    this._rafId = requestAnimationFrame(tick);
  }
}

customElements.define('creature-sprite', CreatureSprite);
export { CreatureSprite };
