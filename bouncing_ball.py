#!/usr/bin/env python3
"""
Bouncing Ball in a Square — Physics Simulation
================================================
A ball bounces inside a square boundary with:
  • Gravity (9.81 m/s² downward)
  • Restitution (0.82 — energy loss on bounce)
  • Elastic wall collisions
  • Velocity trail
  • Real-time energy display (KE / PE / total)

Run directly:   python bouncing_ball.py
Dependencies:   numpy, matplotlib
"""

import os
import sys

# ---------------------------------------------------------------------------
#  Workaround for sandboxed / read-only environments (e.g. Docker, CI)
# ---------------------------------------------------------------------------
_MPL_CACHE = os.environ.get('MPLCONFIGDIR', '')
if not _MPL_CACHE or not os.access(_MPL_CACHE, os.W_OK):
    _tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mplcache')
    os.environ['MPLCONFIGDIR'] = _tmp
    os.makedirs(_tmp, exist_ok=True)

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle

# ===================================================================
#  PHYSICS CONFIGURATION
# ===================================================================
SQUARE_SIZE = 10.0          # width & height of the bounding square
DT          = 0.025         # simulation timestep (seconds ≈ 40 fps)
GRAVITY     = 9.81          # gravitational acceleration (m/s²)
RESTITUTION = 0.82          # coefficient of restitution (1.0 = perfectly elastic)
BALL_RADIUS = 0.4           # ball radius (visual units)

# Effective boundary half-length accounting for ball radius
HALF = SQUARE_SIZE / 2 - BALL_RADIUS

# ===================================================================
#  INITIAL STATE
# ===================================================================
pos = np.array([-2.0, 4.0], dtype=float)   # starting position (x, y)
vel = np.array([4.5, 1.0],  dtype=float)   # starting velocity (vx, vy)

# ===================================================================
#  PHYSICS STEP
# ===================================================================
def physics_step(p, v):
    """Advance the ball by one timestep with gravity and wall collisions."""
    # 1. Apply gravity (downward acceleration)
    v[1] -= GRAVITY * DT

    # 2. Euler integration
    new_p = p + v * DT
    new_v = v.copy()

    # 3. Collision detection & response (reflect + restitution)
    #    Floor
    if new_p[1] < -HALF:
        new_p[1] = -HALF
        new_v[1] = -new_v[1] * RESTITUTION
    #    Ceiling
    if new_p[1] > HALF:
        new_p[1] = HALF
        new_v[1] = -new_v[1] * RESTITUTION
    #    Left wall
    if new_p[0] < -HALF:
        new_p[0] = -HALF
        new_v[0] = -new_v[0] * RESTITUTION
    #    Right wall
    if new_p[0] > HALF:
        new_p[0] = HALF
        new_v[0] = -new_v[0] * RESTITUTION

    return new_p, new_v

# ===================================================================
#  FIGURE SETUP
# ===================================================================
fig, ax = plt.subplots(figsize=(7, 7))
fig.patch.set_facecolor('#f0f0f0')
ax.set_xlim(-SQUARE_SIZE / 2, SQUARE_SIZE / 2)
ax.set_ylim(-SQUARE_SIZE / 2, SQUARE_SIZE / 2)
ax.set_aspect('equal')
ax.set_facecolor('#fafafa')
ax.grid(True, alpha=0.2)
ax.set_title('Bouncing Ball in a Square', fontsize=14, fontweight='bold')

# Square boundary
square = plt.Rectangle(
    (-SQUARE_SIZE / 2, -SQUARE_SIZE / 2),
    SQUARE_SIZE, SQUARE_SIZE,
    fill=False, edgecolor='#2c3e50', linewidth=3, zorder=1
)
ax.add_patch(square)

# Ball
ball = Circle(
    (pos[0], pos[1]), BALL_RADIUS,
    color='#3498db', ec='#2980b9', lw=2, zorder=3
)
ax.add_patch(ball)

# Trail
trail_x, trail_y = [], []
trail_line, = ax.plot(
    [], [], color='#3498db', alpha=0.25, lw=2, zorder=2
)

# HUD overlay
hud = ax.text(
    -4.8, 5.5, '', fontsize=9, fontfamily='monospace',
    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
              edgecolor='#cccccc', alpha=0.85)
)

# ===================================================================
#  ANIMATION LOOP
# ===================================================================
def animate(frame):
    global pos, vel, trail_x, trail_y

    # --- physics ---
    pos, vel = physics_step(pos, vel)

    # --- update ball ---
    ball.set_center((pos[0], pos[1]))

    # --- trail ---
    trail_x.append(pos[0])
    trail_y.append(pos[1])
    if len(trail_x) > 40:
        trail_x.pop(0)
        trail_y.pop(0)
    trail_line.set_data(trail_x, trail_y)

    # --- HUD: kinetic, potential, total energy ---
    ke = 0.5 * (vel[0]**2 + vel[1]**2)
    pe = GRAVITY * (pos[1] + HALF)
    hud.set_text(
        f'frame {frame:3d}  '
        f'KE {ke:5.1f}  PE {pe:5.1f}  E {ke+pe:5.1f}'
    )

    return ball, trail_line, hud


# ===================================================================
#  RUN
# ===================================================================
if __name__ == '__main__':
    print("Bouncing Ball Physics Simulation")
    print("=" * 32)
    print(f"  Square size : {SQUARE_SIZE}×{SQUARE_SIZE}")
    print(f"  Gravity     : {GRAVITY} m/s²")
    print(f"  Restitution : {RESTITUTION}")
    print(f"  Time step   : {DT*1000:.1f} ms")
    print(f"  Frames      : 400")
    print("=" * 32)
    print("Close the window to exit.\n")

    ani = animation.FuncAnimation(
        fig, animate, frames=400,
        interval=DT * 1000, blit=True
    )

    plt.tight_layout()
    plt.show()
