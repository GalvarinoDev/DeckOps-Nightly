# DeckOps Nightly

<p align="center">
  <img src="assets/images/DeckOps-banner.png" alt="DeckOps - CombatOnDeck" width="460"/>
</p>

<p align="center">
  Bringing the Golden Age of FPS to your Steam Deck, no tinkering required.
</p>

---

> **This is the Nightly build of DeckOps. It is unstable and may be broken at any time. Features are experimental and not ready for general use. For the stable release, visit the [main DeckOps repository](https://github.com/GalvarinoDev/DeckOps).**

---

DeckOps automates the installation of CoD4x, IW3SP-MOD, iw4x, T6SP-Mod, and Plutonium on Steam Deck. Pick your games, hit install, and launch them straight from Steam like any other game.

---

## Installation and Uninstall

1. Press the Steam button -> **Power** -> **Switch to Desktop**
2. Open a browser and navigate to this GitHub page
3. Download the **[DeckOps Nightly file](https://github.com/GalvarinoDev/DeckOps-Nightly/releases/download/v1/DeckOps-Nightly.desktop.download)**
4. Right-click the file -> **Properties** -> **Permissions** -> tick **"Is executable"** -> OK
5. Double-click it
   - **First time:** DeckOps installs automatically
   - **Already installed:** A menu appears - choose to Launch, Reinstall, or Uninstall

> Your Steam games are never touched. Only files created by DeckOps are removed during uninstall.

---

## Microsoft Store, CD, or Other Storefronts

DeckOps Nightly supports games purchased outside of Steam, including the Microsoft Store, CD copies, GOG, and other storefronts. To use this feature:

1. Open Steam -> **Games** -> **Add a Non-Steam Game to My Library**
2. Browse to your game executable and add it
3. Launch the game at least once through Steam to create the Proton prefix
4. Run DeckOps Nightly and select **My Own** when asked how you installed your games

DeckOps will automatically detect your games by their exe name, rename the shortcuts to the correct titles, download Steam artwork, and set up mod clients, controller profiles, and display configs just like it does for Steam purchases. No manual renaming required.

> This feature is experimental and actively being developed in the Nightly build.

---

## License

[MIT License](LICENSE)
