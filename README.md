# DeckOps Nightly

<p align="center">
  <img src="assets/images/DeckOps-banner.png" alt="DeckOps - CombatOnDeck" width="460"/>
</p>

<p align="center">
  Bringing <del>the Golden Age of</del> a lot of Call of Duty games to your <del>Steam Deck</del> Immutable Linux device, no tinkering required.™️
</p>

---

> **This is the Nightly build of DeckOps. It is unstable and may be broken at any time. Features are experimental and not ready for general use. For the stable release, visit the [main DeckOps repository](https://github.com/GalvarinoDev/DeckOps).**

---

## 🎮 Supported Games

| Game | Mode | Client | Online | Aim Assist | Gyro |
|---|---|---|---|---|---|
| Modern Warfare | SP | [IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod) | — | ✅ | ✅ |
| Modern Warfare | MP | [CoD4x](https://cod4x.ovh) | ✅ | ❌ | ✅ |
| World at War | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Modern Warfare 2 | SP | — | — | ❌ | ✅ |
| Modern Warfare 2 | MP | [iw4x](https://iw4x.io) | ✅ | ✅ | ✅ |
| Black Ops | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Modern Warfare 3 | SP | — | — | ❌ | ✅ |
| Modern Warfare 3 | MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops II | SP/ZM/MP | [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) + [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Ghosts | SP/MP | [AlterWare](https://alterware.dev) | ✅ | ✅ | ✅ |
| Advanced Warfare | SP/MP | [AlterWare](https://alterware.dev) | ✅ | ✅ | ✅ |
| Black Ops III | SP/MP/ZM | [CleanOps](https://github.com/notnightwolf/cleanopsT7) + [T7x](https://alterware.dev) | ✅ | ✅ | ✅ |

> All titles support controller and gyro via Steam Input. During setup you choose whether to enable gyro and which activation mode you want (ADS, Hold, or Toggle). Aim assist is unavailable for MW1 MP, MW2 SP, and MW3 SP.

---

## 🆕 What's New in Nightly

- **LCD Online Play.** Plutonium online multiplayer now works on LCD Steam Decks. All seven Plutonium titles can connect to online servers from both LCD and OLED hardware. A [free Plutonium account](https://forum.plutonium.pw/register) is required. This is not ban evasion. DeckOps does not bypass or interfere with Plutonium's anti-cheat in any way, no fingerprinting is removed. We use the same methods they recommend the average Linux user to use during installation. This prevents it from triggering the false positive ban and you can enjoy Plutonium servers just like an OLED user would.
- **Multi-Device Support.** Steam Machine, Legion Go/Go S/Go 2, ROG Ally/Ally X/Xbox Ally X, MSI Claw 8, and PCs. Bazzite and CachyOS supported.
- **Controller Templates.** 44 templates across Steam Controller 2 (Triton), PS5/PS5 Edge, PS4, Xbox 360/One/Elite, and generic. Only your device's Neptune variant is installed on top of 28 universal templates.
- **Hold and Toggle Gyro.** Steam Deck LCD/OLED get four gyro modes. Other devices get On or Off.
- **Ghosts & Advanced Warfare.** Singleplayer and multiplayer via AlterWare (IW6-Mod and S1-Mod).
- **Black Ops III.** CleanOps + optional T7x.
- **Black Ops II Singleplayer.** Supported via [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) by Rattpak. DeckOps installs the mod client and deploys display settings automatically. Please be aware their mod is still in the Beta process, they've been gracious enough to let us use it despite it not being fully released on their github.
- **Non-Steam Game Support.** Place game files in `~/Games` and select **Steam & Non-Steam** during setup.
- **Offline LAN Launcher.** Play Plutonium games offline with bots from Game Mode, no account required.
- **Player Name.** Set during setup, pre-filled from Steam. Used in CoD4x, IW4x, AlterWare, T7X, and Plutonium offline.
- **Save Backup & Restore.** Save data backed up before uninstall, restorable after reinstall.
- **No More Protontricks.** Dependencies copied from GE-Proton directly. Shared DLL directory with symlinks cuts prefix size from ~725MB to ~120MB.
- **Menu Mods.** Custom DeckOps UI mods for BO2 MP, BO2 Zombies, and MW3 MP.
- **UI Overhaul.** Setup flow rebuilt with dedicated modules. New flow: OS → Device → Gyro → Name → Source.

---

## 🚧 WIP / Coming Soon

- **Docked Mode / Decky Plugin.** Play on a TV or monitor with an external controller. Auto-switch display settings when you dock and undock. Feature-complete, pending docked hardware testing.
- **InputPlumber dbus integration** to autodetect your device and controller settings.
- **Add Games from My Games screen** without re-running the full setup wizard.

---

## ⚠️ Before You Install

Install your games on Steam first, then install DeckOps. No need to launch any game beforehand. DeckOps creates Proton prefixes automatically for every game.

Plutonium online play requires a [free account](https://forum.plutonium.pw/register) and works on both LCD and OLED Steam Decks. LCD users who only want to play offline do not need a Plutonium account. DeckOps automatically launches all Plutonium games in offline LAN mode on LCD when no account is configured.

Make sure you have a stable internet connection before installing. If the install fails, don't re-run it repeatedly. Join the Discord for help instead.

---

## 💾 Installation & Uninstall

1. Press the Steam button -> **Power** -> **Switch to Desktop**
2. Open a browser and navigate to this GitHub page
3. Download the **[DeckOps Nightly file](https://github.com/GalvarinoDev/DeckOps-Nightly/releases/download/v1/DeckOps-Nightly.desktop)**
4. Right-click the file -> **Properties** -> **Permissions** -> tick **"Is executable"** -> OK
5. Double-click it
   - **First time:** DeckOps installs automatically and launches when finished
   - **Already installed:** A menu appears with options to Launch or Uninstall

DeckOps checks for updates on every launch. Updates are incremental when possible, only downloading changed files. Your config (`deckops.json`), logs, and background music are never overwritten during updates.

> Your Steam games are never touched. Only files created by DeckOps are removed during uninstall. The uninstaller backs up your save data before removing anything.

---

## ⚠️ After Installation

**Click Continue when installation finishes, DeckOps will reopen Steam automatically.** First launches take longer while Proton sets things up.

If Steam asks about cloud saves, choose **Keep Local**. If asked about safe mode or hardware changes, choose **No**.

- **MW1 and WaW** have separate DeckOps multiplayer shortcuts. Use the main entry for SP, the DeckOps shortcut for MP. MW1 SP: select the "Player" profile on first launch.
- **MW2 MP (Non-Steam).** IW4x must be launched twice on first install. The first launch will fail, relaunch and it works.
- **Black Ops III.** Do the first launch in Desktop Mode. Launch T7X first if installed, close it, then launch BO3. CleanOps will patch the game and won't launch after patching. Press Stop in Steam and relaunch. After this, both work fine in Game Mode.
- **LCD Steam Deck.** Plutonium games may take a moment to launch (shader cache cleanup). Skip Vulkan shader compilation if prompted. Quit from the in-game menu for a faster exit.

---

## 🎮 Gyro Controls

DeckOps installs a controller profile for every game. Choose your gyro mode during setup or change it anytime in **Settings > Controller Profiles > Re-apply Templates**. R5 is push-to-talk in all modes.

| Mode | How it works | Devices |
|---|---|---|
| **ADS** | Gyro activates when you aim down sights | Steam Deck, Steam Machine |
| **Hold** | Gyro activates while L5 is held | Steam Deck, Steam Machine |
| **Toggle** | L5 press on / L5 press off | Steam Deck, Steam Machine |
| **On / Off** | Simple toggle | Legion Go, ROG Ally, MSI Claw 8, PC |

MW1 MP, MW2 SP, and MW3 SP handle gyro differently due to controller support added via Steam Input.

---

## 🛠️ My Games Screen

The My Games screen shows every supported game as a card with header art and a client badge. Each card has a **Configure** button with options for Mods (open mod/user map folders), Update (re-download the mod client), and Reinstall. Unconfigured games show a **Set Up** button instead. The Plutonium Offline card has a **Re-Add** button. The header bar includes **Guide** and **Settings** buttons.

---

## ⚙️ Settings

| Option | What it does |
|---|---|
| Background Music | Toggle on/off and adjust volume |
| Controller Profiles | Switch gyro mode (ADS, Hold, Toggle, Off) and re-apply controller templates to all games |
| Player Name | Change your in-game name for CoD4x, IW4x, AlterWare (Ghosts, AW), T7X, and Plutonium offline LAN mode. Does not affect CleanOps. |
| Shader Cache (LCD only) | Clear shader cache data for all set-up games |
| Check for Updates | Check for and apply DeckOps updates |
| Full Uninstall | Remove everything DeckOps installed (backs up save data first) |
| Reset DeckOps Config | Wipe DeckOps config and run setup again |
| Links | Quick links to the Discord, Stable repo, and Nightly repo |

---

## 🔧 Troubleshooting

https://discord.gg/bkSQeq5Azk

## Credits

DeckOps is an installer. This project wouldn't exist without the years of foundational work from these teams. They truly deserve all the credit:

**[CoD4x](https://cod4x.ovh)** - Modern Warfare 1 Multiplayer client. [GitHub](https://github.com/callofduty4x)

**[IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod)** - Modern Warfare 1 Singleplayer client by [JerryALT](https://gitea.com/JerryALT).

**[iw4x](https://iw4x.io)** - Modern Warfare 2 Multiplayer client. [GitHub](https://github.com/iw4x)

**[AlterWare](https://alterware.dev)** - Ghosts and Advanced Warfare client (IW6-Mod and S1-Mod). Black Ops III T7x client. [GitHub](https://github.com/alterware)

**[CleanOps](https://github.com/notnightwolf/cleanopsT7)** - Black Ops III mod by [notnightwolf](https://github.com/notnightwolf).

**[T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release)** - Black Ops II Singleplayer client by [Rattpak](https://github.com/Rattpak).

**[Plutonium](https://plutonium.pw)** - Modern Warfare 3, World at War, Black Ops, and Black Ops II client. 💰 [Donate](https://forum.plutonium.pw/donate)

Official Test Team: LeFinnaBust & Special Agent Dale Cooper

---
**[Call of Duty Alt Launcher](https://github.com/framilano/CallofDutyAltLauncher)** - Inspiration for DeckOps.

**[LanLauncher](https://github.com/JugAndDoubleTap/LanLauncher)** - Inspiration for LCD offline LAN mode.

Steam artwork from [SteamGridDB](https://www.steamgriddb.com) - thanks to [Moohoo](https://www.steamgriddb.com/profile/76561198009314736), [jarvis](https://www.steamgriddb.com/profile/76561198103947979), [Ramjez](https://www.steamgriddb.com/profile/76561198122547176), [Over](https://www.steamgriddb.com/profile/76561198049670875), [Uravity-PRO](https://www.steamgriddb.com/profile/76561198167607660), [Maxine](https://www.steamgriddb.com/profile/76561198130550992), [caukyy](https://www.steamgriddb.com/profile/76561198031582867), [Middle](https://www.steamgriddb.com/profile/76561198027273869), [Hevi](https://www.steamgriddb.com/profile/76561198018073166), [europeOS](https://www.steamgriddb.com/profile/76561198038608428), [Empti](https://www.steamgriddb.com/profile/76561198022992095), [grimlokk](https://www.steamgriddb.com/profile/76561199034037601), [Mr.Parks](https://www.steamgriddb.com/profile/76561198018403239), [Dankheili](https://www.steamgriddb.com/profile/76561198040056867), [FaN](https://www.steamgriddb.com/profile/76561198015449572), [adamboulton](https://www.steamgriddb.com/profile/76561198143575007), [ActualCj](https://www.steamgriddb.com/profile/76561198135110632), [KimaRo](https://www.steamgriddb.com/profile/76561197985524535), [Gector(lint)Nathan](https://www.steamgriddb.com/profile/76561198319864298), [increasing](https://www.steamgriddb.com/profile/76561198041593264), [xamon](https://www.steamgriddb.com/profile/76561197979282373), [jakearty](https://www.steamgriddb.com/profile/76561199079444502), [dragnus](https://www.steamgriddb.com/profile/76561198015793633), [Rod](https://www.steamgriddb.com/profile/76561198125292564), and [OnSync](https://www.steamgriddb.com/profile/76561198061208589).

**[Claude](https://claude.ai)** by Anthropic - assisted in development.

---

> DeckOps is not affiliated with Activision, Infinity Ward, Treyarch, or Valve. All trademarks belong to their respective owners. A legitimate copy of each game is required. DeckOps does not provide or distribute game files.

## License

[MIT License](LICENSE)
