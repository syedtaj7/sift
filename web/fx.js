"use strict";
/* Pixel scene (night sky, stars, drifting clouds, parallax hills) and a particle system
   for flight trails, landing bursts and fireworks. Both canvases render at low resolution
   and are upscaled with image-rendering: pixelated for real chunky pixels. */

(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SKY_PX = 4;  // 1 sky pixel = 4 css px
  const FX_PX = 3;   // 1 particle pixel = 3 css px

  const PALETTE = {
    bands: ["#100d22", "#141130", "#19153c", "#211a4b", "#2b1f5c", "#3a246b", "#4f2a76", "#6b2f7a", "#8e3476", "#b53e6e"],
    stars: ["#fff4e0", "#fff4e0", "#ffe14d", "#2ec4ff", "#ff7ac6"],
    hills: ["#4a2a7a", "#331f63", "#22174a", "#150f30"],
    cloud: "#3d2b74",
    cloudHi: "#5a3f96",
  };

  /* ------------------------------------------------------------ sky */
  const sky = document.getElementById("sky");
  const sctx = sky.getContext("2d");
  let W = 0, H = 0, stars = [], clouds = [], hills = [], shooting = null;

  function rand(a, b) { return a + Math.random() * (b - a); }

  function makeHill(L, amp, base, seeds) {
    // periodic height map so it loops seamlessly while scrolling
    const h = new Float32Array(L);
    for (let x = 0; x < L; x++) {
      let y = 0;
      for (const [k, a, p] of seeds) y += a * Math.sin((2 * Math.PI * k * x) / L + p);
      h[x] = base - amp * y;
    }
    return h;
  }

  function resizeSky() {
    W = Math.ceil(innerWidth / SKY_PX);
    H = Math.ceil(innerHeight / SKY_PX);
    sky.width = W; sky.height = H;
    stars = Array.from({ length: Math.round((W * H) / 70) }, () => ({
      x: Math.floor(rand(0, W)), y: Math.floor(rand(0, H * 0.62)),
      c: PALETTE.stars[Math.floor(rand(0, PALETTE.stars.length))],
      t: rand(0, Math.PI * 2), s: rand(0.02, 0.07), big: Math.random() < 0.06,
    }));
    clouds = Array.from({ length: 5 }, (_, i) => ({ x: rand(0, W), y: rand(H * 0.12, H * 0.45), w: Math.floor(rand(16, 34)), v: rand(0.03, 0.09) }));
    const L = W * 2;
    hills = [
      { h: makeHill(L, H * 0.07, H * 0.68, [[2, 1, 0.3], [5, 0.45, 1.7], [11, 0.15, 0.4]]), v: 0.04, c: PALETTE.hills[0], L },
      { h: makeHill(L, H * 0.06, H * 0.76, [[3, 1, 2.1], [7, 0.4, 0.2], [13, 0.18, 1.1]]), v: 0.09, c: PALETTE.hills[1], L },
      { h: makeHill(L, H * 0.05, H * 0.85, [[4, 1, 1.0], [9, 0.5, 2.6], [17, 0.2, 0.8]]), v: 0.17, c: PALETTE.hills[2], L },
      { h: makeHill(L, H * 0.025, H * 0.93, [[6, 1, 0.5], [15, 0.4, 1.9]]), v: 0.3, c: PALETTE.hills[3], L },
    ];
    hills.forEach((l) => (l.off = rand(0, l.L)));
    drawSky(0);
  }

  function drawSky(frame) {
    // dithered gradient bands
    const bands = PALETTE.bands, bh = (H * 0.9) / bands.length;
    for (let i = 0; i < bands.length; i++) {
      sctx.fillStyle = bands[i];
      sctx.fillRect(0, Math.floor(i * bh), W, Math.ceil(bh) + 1);
      if (i < bands.length - 1) {
        sctx.fillStyle = bands[i + 1];
        const y = Math.floor((i + 1) * bh) - 2;
        for (let x = (i % 2); x < W; x += 2) sctx.fillRect(x, y, 1, 1);
        for (let x = ((i + 1) % 2); x < W; x += 4) sctx.fillRect(x, y - 1, 1, 1);
      }
    }
    sctx.fillStyle = bands[bands.length - 1];
    sctx.fillRect(0, Math.floor(H * 0.9), W, H);

    // stars
    for (const s of stars) {
      const tw = Math.sin(s.t + frame * s.s);
      if (tw < -0.55) continue;
      sctx.fillStyle = s.c;
      sctx.fillRect(s.x, s.y, 1, 1);
      if (s.big && tw > 0.6) {
        sctx.fillRect(s.x - 1, s.y, 1, 1); sctx.fillRect(s.x + 1, s.y, 1, 1);
        sctx.fillRect(s.x, s.y - 1, 1, 1); sctx.fillRect(s.x, s.y + 1, 1, 1);
      }
    }

    // moon
    const mx = Math.floor(W * 0.82), my = Math.floor(H * 0.16), r = Math.max(6, Math.floor(H * 0.035));
    for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
      if (x * x + y * y <= r * r) {
        sctx.fillStyle = (x + 2) * (x + 2) + (y - 1) * (y - 1) < 4 || (x - 3) * (x - 3) + (y + 3) * (y + 3) < 3 ? "#e8d6b0" : "#fff4e0";
        sctx.fillRect(mx + x, my + y, 1, 1);
      }
    }

    // shooting star
    if (!reduce && !shooting && Math.random() < 0.004) shooting = { x: rand(W * 0.2, W), y: rand(0, H * 0.25), life: 40 };
    if (shooting) {
      for (let i = 0; i < 8; i++) {
        sctx.fillStyle = i < 2 ? "#fff4e0" : i < 5 ? "#ffe14d" : "#ff7ac6";
        sctx.fillRect(Math.floor(shooting.x + i), Math.floor(shooting.y - i * 0.5), 1, 1);
      }
      shooting.x -= 2.2; shooting.y += 1.1; shooting.life--;
      if (shooting.life <= 0) shooting = null;
    }

    // clouds
    for (const c of clouds) {
      if (!reduce) c.x = (c.x + c.v) % (W + c.w);
      const x = Math.floor(c.x) - c.w, y = Math.floor(c.y);
      sctx.fillStyle = PALETTE.cloud;
      sctx.fillRect(x, y, c.w, 3);
      sctx.fillRect(x + 3, y - 2, c.w - 9, 2);
      sctx.fillRect(x + 7, y - 4, Math.floor(c.w / 3), 2);
      sctx.fillStyle = PALETTE.cloudHi;
      sctx.fillRect(x + 4, y - 2, c.w - 12, 1);
      sctx.fillRect(x + 8, y - 4, Math.floor(c.w / 3) - 2, 1);
    }

    // parallax hills
    for (const l of hills) {
      if (!reduce) l.off = (l.off + l.v) % l.L;
      sctx.fillStyle = l.c;
      for (let x = 0; x < W; x++) {
        const y = Math.floor(l.h[Math.floor(x + l.off) % l.L]);
        sctx.fillRect(x, y, 1, H - y);
      }
    }
  }

  /* ------------------------------------------------------------ particles */
  const fx = document.getElementById("fx");
  const fctx = fx.getContext("2d");
  let FW = 0, FH = 0;
  const parts = [];
  const followers = new Set();

  function resizeFx() {
    FW = Math.ceil(innerWidth / FX_PX);
    FH = Math.ceil(innerHeight / FX_PX);
    fx.width = FW; fx.height = FH;
  }

  function spawn(x, y, color, o = {}) {
    parts.push({
      x: x / FX_PX, y: y / FX_PX,
      vx: o.vx ?? rand(-1, 1), vy: o.vy ?? rand(-1, 1),
      g: o.g ?? 0.04, life: o.life ?? rand(24, 44), max: 0, c: color, size: o.size ?? 1,
    });
    parts[parts.length - 1].max = parts[parts.length - 1].life;
  }

  const FX = {
    /** pixel explosion at a screen point */
    burst(x, y, colors, n = 26) {
      if (reduce) return;
      for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i) / n + rand(-0.2, 0.2), sp = rand(0.6, 2.4);
        spawn(x, y, colors[i % colors.length], { vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 0.6, g: 0.06, size: Math.random() < 0.3 ? 2 : 1 });
      }
    },
    /** emit a sparkle trail behind an element while it flies */
    follow(el, colors) {
      if (reduce) return () => {};
      const f = { el, colors };
      followers.add(f);
      return () => followers.delete(f);
    },
    /** celebratory fireworks across the screen */
    fireworks(colors, rounds = 7) {
      if (reduce) return;
      for (let i = 0; i < rounds; i++) {
        setTimeout(() => {
          const x = rand(innerWidth * 0.15, innerWidth * 0.85), y = rand(innerHeight * 0.12, innerHeight * 0.45);
          const c = colors[i % colors.length];
          for (let k = 0; k < 40; k++) {
            const a = (Math.PI * 2 * k) / 40, sp = rand(1.2, 2.6);
            spawn(x, y, k % 3 ? c : "#fff4e0", { vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, g: 0.035, life: rand(40, 70), size: k % 5 ? 1 : 2 });
          }
        }, i * 380);
      }
    },
    /** floating "+1" style text made of pixels is overkill; use DOM, but give it sparks */
    sparkle(x, y, color) {
      if (reduce) return;
      for (let i = 0; i < 6; i++) spawn(x + rand(-14, 14), y + rand(-8, 8), color, { vx: rand(-.3, .3), vy: rand(-1.2, -.4), g: 0.01, life: rand(18, 30) });
    },
  };
  window.FX = FX;

  function tickFx() {
    fctx.clearRect(0, 0, FW, FH);
    for (const f of followers) {
      if (!f.el.isConnected) { followers.delete(f); continue; }
      const r = f.el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      for (let i = 0; i < 2; i++) {
        spawn(cx + rand(-r.width / 3, r.width / 3), cy + rand(-r.height / 3, r.height / 3),
          f.colors[Math.floor(rand(0, f.colors.length))], { vx: rand(-.4, .4), vy: rand(-.2, .5), g: 0.02, life: rand(14, 26) });
      }
    }
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      p.vy += p.g; p.x += p.vx; p.y += p.vy; p.life--;
      if (p.life <= 0 || p.y > FH + 4) { parts.splice(i, 1); continue; }
      // blink out in the last frames, like old arcade sprites
      if (p.life < p.max * 0.25 && p.life % 2) continue;
      fctx.fillStyle = p.c;
      fctx.fillRect(Math.round(p.x), Math.round(p.y), p.size, p.size);
    }
  }

  /* ------------------------------------------------------------ loop */
  let frame = 0, last = 0;
  function loop(t) {
    requestAnimationFrame(loop);
    if (t - last < 1000 / 40) return; // ~40fps keeps it light and a bit retro
    last = t;
    frame++;
    if (frame % 2 === 0) drawSky(frame);
    tickFx();
  }

  resizeSky();
  resizeFx();
  addEventListener("resize", () => { resizeSky(); resizeFx(); });
  if (!reduce) requestAnimationFrame(loop);
})();
