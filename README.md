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

## LCD Online Play

Plutonium online multiplayer now works on LCD Steam Decks. All seven Plutonium titles (MW3, WaW SP/ZM, WaW MP, BO1 SP/ZM, BO1 MP, BO2 ZM, BO2 MP) can connect to online servers from both LCD and OLED hardware. A [free Plutonium account](https://forum.plutonium.pw/register) is required for online play.

**This is not ban evasion.** DeckOps does not bypass or interfere with Plutonium's anti-cheat in any way. Plutonium retains full ability to ban individual LCD users just as they can any other player. LCD users are subject to the same rules and enforcement as everyone else.

---

## 🎮 Supported Games

| Game | Mode | Client | Online | Aim Assist | Gyro |
|---|---|---|---|---|---|
| Modern Warfare | SP | [IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod) | No | ✅ | ✅ |
| Modern Warfare | MP | [CoD4x](https://cod4x.ovh) | LCD + OLED | ❌ | ✅ |
| Modern Warfare 2 | SP | — | No | ❌ | ✅ |
| Modern Warfare 2 | MP | [iw4x](https://iw4x.io) | LCD + OLED | ✅ | ✅ |
| Modern Warfare 3 | SP | — | No | ❌ | ✅ |
| Modern Warfare 3 | MP | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| World at War | SP + ZM | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| World at War | MP | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| Black Ops | SP + ZM | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| Black Ops | MP | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| Black Ops II | SP | [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) ¹ | No | ❌ | ✅ |
| Black Ops II | ZM | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |
| Black Ops II | MP | [Plutonium](https://plutonium.pw) | LCD + OLED | ✅ | ✅ |

> ¹ Not yet implemented. BO2 SP currently launches through vanilla Steam.

---

## 🆕 What's New in Nightly

**Non-Steam Game Support** · Games from the Microsoft Store, retail CD copies, and other storefronts are now supported. Place your game files in `~/Games` and select **Steam & Non-Steam** during setup. DeckOps scans for your games and handles shortcuts, artwork, Proton prefixes, mod clients, controller profiles, and display configs automatically.

**Offline LAN Launcher** · A dedicated Game Mode launcher for playing Plutonium games offline with bots. Shows installed games with mode buttons (MP, SP, Zombies), supports full gamepad navigation, and works on both LCD and OLED without a Plutonium account.

**Player Name** · Set your in-game name during setup, pre-filled from your Steam display name. Used in CoD4x, IW4x, and Plutonium offline LAN mode. Change it anytime in Settings.

**Docked Mode** · Play on a TV or monitor with an external controller. Choose your display resolution and controller type (PlayStation, Xbox, or Generic) during setup. A Decky Loader plugin is available to auto-switch display settings when you dock and undock.

**No More Protontricks** · All runtime dependencies are now copied directly from GE-Proton's built-in prefix. Faster installs, fewer failure points, no external tools.

**Shader Cache Cleanup** · LCD Plutonium games automatically clear junk shader cache data on every launch, preventing accumulation from a Steam bug with non-Steam shortcuts.

**Menu Mods** · Custom DeckOps UI mods for BO2 Multiplayer, BO2 Zombies, and MW3 Multiplayer, installed automatically during setup.

---

## 💾 Installation & Uninstall

1. Press the Steam button -> **Power** -> **Switch to Desktop**
2. Open a browser and navigate to this GitHub page
3. Download the **[DeckOps Nightly file](https://github.com/GalvarinoDev/DeckOps-Nightly/releases/download/v1/DeckOps-Nightly.desktop)**
4. Right-click the file -> **Properties** -> **Permissions** -> tick **"Is executable"** -> OK
5. Double-click it
   - **First time:** DeckOps installs automatically
   - **Already installed:** A menu appears with options to Launch, Reinstall, or Uninstall

> Your Steam games are never touched. Only files created by DeckOps are removed during uninstall.

---

## 🔧 Troubleshooting

https://discord.gg/bkSQeq5Azk

## Credits

DeckOps is an installer. This project wouldn't exist without the years of foundational work from these teams:

**[CoD4x](https://cod4x.ovh)** · **[IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod)** · **[iw4x](https://iw4x.io)** · **[T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release)** · **[Plutonium](https://plutonium.pw)** 💰 [Donate](https://forum.plutonium.pw/donate)

Official Test Team: LeFinnaBust & Special Agent Dale Cooper

**[PlutoniumAltLauncher](https://github.com/framilano/PlutoniumAltLauncher)** · **[LanLauncher](https://github.com/JugAndDoubleTap/LanLauncher)** · Inspiration for DeckOps.

Steam artwork from [SteamGridDB](https://www.steamgriddb.com).

**[Claude](https://claude.ai)** by Anthropic · assisted in development.

---

> DeckOps is not affiliated with Activision, Infinity Ward, Treyarch, or Valve. All trademarks belong to their respective owners. A legitimate copy of each game is required. DeckOps does not provide or distribute game files.

## License

[MIT License](LICENSE)
