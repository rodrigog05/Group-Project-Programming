# Foundry Town for the browser

Use the same repository and the browser-version branch. The browser build combines the desktop Town model with pygame-ce rendering. prepare.py stages the shared Python modules, world maps and browser frontend under browser_game/build/game. Tkinter and SQLite are not required by the running browser.

## Play and build

From the repository root, with Python 3.12:

```
python -m pip install -r browser_game/requirements.txt
python browser_game/prepare.py
python -m pygbag browser_game/build/game
```

Open the address printed by Pygbag and click to activate the game. Move with WASD or the arrows. Press E to enter and E again to trade. At Goldenfield Farm, Q buys up to four wheat, and F/R buy eggs. Esc returns to the street. Sunrise Bakery is east of the farm. Daily Bread Market is west along the same road. P opens the directory. Browser storage keeps this origin's progress between visits. The external Pygbag runtime requires internet on first load.

For Pages, run `python -m pygbag --build browser_game/build/game` after staging. Serve the contents of browser_game/build/game/build/web under the repository's project path. Only publish a build after a browser playtest. The generated archives are deployment files.

## Coverage checklist

- [x] Chromium keyboard playthrough of Goldenfield Farm → Sunrise Bakery → Daily Bread Market. One wheat cost $4, production took four active seconds, and the market paid $14 for the loaf.
- [x] Original day/night city, building collisions, camera, shared economy and illustrated supplier, factory and market interiors included in the build.
- [x] Local saves use the desktop snapshot format and a dedicated browser storage key.
- [ ] Finish verifying services, automation, character customization, sound and advanced progression in the browser.
- [ ] Verify live Pages endpoint and additional browsers.
