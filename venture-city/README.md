# Venture City — Business Tycoon

Grow six businesses, upgrade passive income, and earn milestone rewards. All money is virtual.

## Run locally

From this folder run `python3 -m http.server 8000` (or `python -m http.server 8000` on Windows), then open http://localhost:8000.

No build step, dependencies, or API key required. Progress saves in browser local storage with up to four hours of offline earnings.

## API integration

Frankfurter supplies live EUR exchange rates: https://api.frankfurter.app/latest?from=EUR&to=USD,GBP,JPY

The EUR/USD rate scales logistics and technology income between 0.8× and 1.3×. Data refreshes every five minutes. If unavailable, a neutral 1× fallback keeps the game running.

## Files

- index.html — interface
- style.css — responsive layout
- game.js — simulation, upgrades, milestones, saves, API

This browser game is independent of the Foundry Town game in the repository root.
