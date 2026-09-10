# DeckOps Nightly

<p align="center">
  <img src="assets/images/DeckOps-banner.png" alt="DeckOps - CombatOnDeck" width="460"/>
</p>

<p align="center">
  Bringing the Golden Age of Call of Duty to your Steam Deck, Steam Box, and Linux handhelds, no tinkering required.™
</p>

---

> **This is the Nightly build of DeckOps. It is unstable and may be broken at any time. Features are experimental and not ready for general use. For the stable release, visit the [main DeckOps repository](https://github.com/GalvarinoDev/DeckOps).**

---

## 🎮 Supported Games

| Game | Mode | Client | Online | Aim Assist | Gyro |
|---|---|---|---|---|---|
| Modern Warfare | SP/MP | [IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod) + [CoD4R](https://github.com/Divity) | ✅ | ✅ | ✅ |
| World at War | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Modern Warfare 2 | MP | [iw4x](https://iw4x.io) | ✅ | ✅ | ✅ |
| Black Ops | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Modern Warfare 3 | MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops II | SP/ZM/MP | [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) + [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops III | SP/MP/ZM | [CleanOps](https://github.com/notnightwolf/cleanopsT7) + [T7x](https://github.com/alterware) | ✅ | ✅ | ✅ |

> All titles support controller and gyro through Steam Input. During setup, you choose whether to turn on gyro and which activation mode you want (ADS, Hold, or Toggle). Aim assist is not available for MW2 SP and MW3 SP. CoD4x is available as an alternative MW1 MP client during setup.

---

## 🆕 What's New in Nightly

- **LCD Online Play.** Plutonium online multiplayer now works on LCD Steam Decks. All seven Plutonium titles can connect to online servers from both LCD and OLED hardware. A [free Plutonium account](https://forum.plutonium.pw/register) is required. This is not ban evasion. DeckOps does not bypass or interfere with Plutonium's anti-cheat system, and it does not remove any fingerprinting. DeckOps uses the same setup method that Plutonium recommends for the average Linux user. This method avoids the false positive ban, so LCD users can join Plutonium servers the same way OLED users do.
- **Multi-Device Support.** Steam Machine, Legion Go/Go S/Go 2, ROG Ally/Ally X/Xbox Ally X, MSI Claw 8, and PCs. Bazzite and CachyOS are supported.
- **Controller Templates.** 44 templates across Steam Controller 2 (Triton), PS5/PS5 Edge, PS4, Xbox 360/One/Elite, and generic. DeckOps installs only your device's Neptune variant on top of 28 universal templates.
- **Hold and Toggle Gyro.** Steam Deck LCD/OLED get four gyro modes. Other devices get On or Off.
- **Black Ops III.** CleanOps plus optional T7x.
- **Black Ops II Singleplayer.** Supported through [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) by Rattpak. DeckOps installs the mod client and sets the display settings automatically. Note: the mod is still in beta. Rattpak has generously allowed DeckOps to use it ahead of its full release on GitHub.
- **MW3 Downgrade.** A Steam update to MW3 breaks Plutonium. DeckOps detects the broken install and downgrades it during setup. You can also start a downgrade from My Games. Two methods: scan a QR code with the Steam mobile app (recommended), or paste commands into the Steam console.
- **Non-Steam Game Support.** Place game files in `~/Games` and select **Steam & Non-Steam** during setup.
- **Offline LAN Launcher.** Play Plutonium games offline with bots from Game Mode. No account required.
- **CoD4R (Call of Duty 4: Revived).** New default MW1 multiplayer client by [k/divity](https://github.com/Divity), with native controller support, aim assist, a server browser, quality-of-life improvements, and bot support. CoD4R is a new project, and its server list and player base are growing. CoD4x remains available as an alternative during setup. [Discord](https://discord.com/invite/uWAuFzru34)
- **Player Name.** Set during setup and pre-filled from Steam. Used in CoD4x, IW4x, T7X, and Plutonium offline.
- **Save Backup & Restore.** DeckOps backs up save data before uninstall and restores it after reinstall.
- **No More Protontricks.** DeckOps copies dependencies directly from GE-Proton. A shared DLL directory with symlinks cuts prefix size from about 725MB to about 120MB.
- **Menu Mods.** Custom DeckOps UI mods for BO2 MP, BO2 Zombies, and MW3 MP.
- **UI Overhaul.** DeckOps rebuilt the setup flow with dedicated modules. New flow: OS → Device → Gyro → Name → Source.

---

## 🚧 WIP / Coming Soon

- **Docked Mode / Decky Plugin.** Play on a TV or monitor with an external controller. Display settings switch automatically when you dock and undock. This feature is complete and awaits testing on docked hardware.
- **InputPlumber dbus integration** to autodetect your device and controller settings.
- **Add Games from My Games screen** without running the full setup wizard again.

---

## ⚠️ Before You Install

Install your games on Steam first, then install DeckOps. You do not need to launch any game beforehand. DeckOps creates Proton prefixes automatically for every game.

Plutonium online play requires a [free account](https://forum.plutonium.pw/register) and works on both LCD and OLED Steam Decks. LCD users who only want offline play do not need a Plutonium account. When no account is configured, DeckOps automatically launches all Plutonium games in offline LAN mode on LCD.

Make sure you have a stable internet connection before you install. If the install fails, do not re-run it many times. Join the Discord for help instead.

---

## 💾 Installation & Uninstall

1. Press the Steam button -> **Power** -> **Switch to Desktop**
2. Open a browser and navigate to this GitHub page
3. Download the **[DeckOps Nightly file](https://github.com/GalvarinoDev/DeckOps-Nightly/releases/download/v1/DeckOps-Nightly.desktop)**
4. Right-click the file -> **Properties** -> **Permissions** -> tick **"Is executable"** -> OK
5. Double-click it
   - **First time:** DeckOps installs automatically and launches when finished
   - **Already installed:** A menu appears with options to Launch or Uninstall

DeckOps checks for updates on every launch. Updates are incremental when possible and download only the changed files. Your config (`deckops.json`), logs, and background music are never overwritten during updates.

> DeckOps never touches your Steam games. Uninstall removes only the files DeckOps created. The uninstaller backs up your save data before it removes anything.

---

## ⚠️ After Installation

**Click Continue when installation finishes. DeckOps then reopens Steam automatically.** First launches take longer while Proton sets things up.

If Steam asks about cloud saves, choose **Keep Local**. If asked about safe mode or hardware changes, choose **No**.

- **MW1 and WaW** have separate DeckOps multiplayer shortcuts. Use the main entry for SP and the DeckOps shortcut for MP. MW1 SP: select the "Player" profile on first launch. MW1 MP (CoD4R): the CoD4R launcher runs during install to download mod files. Close it when the download finishes.
- **MW2 MP (Non-Steam).** Launch IW4x twice on first install. The first launch fails. Relaunch it and it works.
- **Black Ops III.** Do the first launch in Desktop Mode. Launch Black Ops III first so CleanOps can patch it. If it does not launch after patching, press Stop in Steam and relaunch. If you installed T7X, launch it after CleanOps is working. After this, both work fine in Game Mode.
- **LCD Steam Deck.** Plutonium games may take a moment to launch during shader cache cleanup. Skip Vulkan shader compilation if prompted. Quit from the in-game menu for a faster exit.

---

## 🎮 Gyro Controls

DeckOps installs a controller profile for every game. Choose your gyro mode during setup, or change it anytime in **Settings > Controller Profiles > Re-apply Templates**. R5 is push-to-talk in all modes.

| Mode | How it works | Devices |
|---|---|---|
| **ADS** | Gyro activates when you aim down sights | Steam Deck, Steam Machine |
| **Hold** | Gyro activates while L5 is held | Steam Deck, Steam Machine |
| **Toggle** | L5 press on / L5 press off | Steam Deck, Steam Machine |
| **On / Off** | Simple toggle | Legion Go, ROG Ally, MSI Claw 8, PC |

MW1 MP, MW2 SP, and MW3 SP handle gyro differently because of controller support added through Steam Input.

---

## 🛠️ My Games Screen

The My Games screen shows every supported game as a card with header art and a client badge. Each card has a **Configure** button with options for Mods (open mod/user map folders), Update (re-download the mod client), and Reinstall. Unconfigured games show a **Set Up** button instead. The Plutonium Offline card has a **Re-Add** button. The header bar includes **Guide** and **Settings** buttons.

---

## ⚙️ Settings

| Option | What it does |
|---|---|
| Background Music | Turn on/off and adjust volume |
| Controller Profiles | Switch gyro mode (ADS, Hold, Toggle, Off) and re-apply controller templates to all games |
| Player Name | Change your in-game name for CoD4R, CoD4x, IW4x, T7X, and Plutonium offline LAN mode. Does not affect CleanOps. |
| Shader Cache (LCD only) | Clear shader cache data for all set-up games |
| Check for Updates | Check for and apply DeckOps updates |
| Full Uninstall | Remove everything DeckOps installed (backs up save data first) |
| Reset DeckOps Config | Wipe DeckOps config and run setup again |
| Links | Quick links to the Discord, Stable repo, and Nightly repo |

---

## 🔧 Troubleshooting

https://discord.gg/bkSQeq5Azk

## Credits

DeckOps is an installer. This project would not exist without years of foundational work from these teams. They deserve full credit:

**[CoD4R](https://github.com/Divity)** - Modern Warfare 1 Multiplayer client (Call of Duty 4: Revived) by [k/divity](https://github.com/Divity). Native controller support, aim assist, server browser, and bot support. A new project with a growing community. [Discord](https://discord.com/invite/uWAuFzru34) | 💰 [Ko-fi](https://ko-fi.com/divity)

**[CoD4x](https://cod4x.ovh)** - Modern Warfare 1 Multiplayer client (alternative). [GitHub](https://github.com/callofduty4x)

**[IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod)** - Modern Warfare 1 Singleplayer client by [JerryALT](https://gitea.com/JerryALT).

**[iw4x](https://iw4x.io)** - Modern Warfare 2 Multiplayer client. [GitHub](https://github.com/iw4x)

**[AlterWare](https://github.com/alterware)** - Black Ops III T7x client. Ghosts (IW6-Mod) and Advanced Warfare (S1-Mod) support was discontinued by the developer in September 2026.

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
