# Footer game prototype

Open [index.html](./index.html) in a browser. No installation, build, or website
server is required.

This is a standalone copy of the pixel-runner footer from the **Open footer
prototype** session in the `vscode-website` workspace, copied on October 22, 2026.
The original website and session preview are unchanged.

- `game.js`: the original runner logic, without unrelated homepage interactions.
- `game.css`: the runner styles compiled from the original website styles,
  including touch controls, reduced motion, and forced colors.
- `assets/`: the original player and obstacle SVGs.

The standalone page supplies the website's base font, color variables, and
box-sizing. Its Jump icon is inline SVG instead of requiring the website's icon
font. Release notes links open on `code.visualstudio.com` rather than a local
website route. The original prototype's naming-prize text is retained; this
standalone copy does not implement submissions or prizes.

## Controls

- **Start / Run again**: start or restart the game.
- **Space, Up Arrow, or W**: jump while the game area has focus.
- **Escape / Pause**: pause; **Resume** continues the game.
- While idle, paused, or after game over, drag/swipe or use **Left / Right,
  Home / End** to browse releases. **Tab** focuses visible release links.
- **Enter** on the game area opens the release notes beneath the character.
- On touch devices, use the **Jump** and **Pause** buttons.

With reduced motion enabled, animation is disabled and release browsing remains
available.

Nothing in this folder creates a GitHub repository or publishes the prototype.
