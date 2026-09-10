# DeckOps Nightly

<p align="center">
  <img src="assets/images/DeckOps-banner.png" alt="DeckOps - CombatOnDeck" width="460"/>
</p>

<p align="center">
  Bringing the Golden Age of Call of Duty to your Steam Deck and other Linux handhelds and devices, no tinkering required.™️
</p>

---

> **This is the Nightly build of DeckOps. It is unstable and may be broken at any time. Features are experimental and not ready for general use. For the stable release, visit the [main DeckOps repository](https://github.com/GalvarinoDev/DeckOps).**

---

## Supported Games

| Game | Mode | Client | Online | Aim Assist | Gyro |
|---|---|---|---|---|---|
| Modern Warfare | SP/MP | [IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod) + [CoD4R](https://github.com/Divity) | ✅ | ✅ | ✅ |
| Modern Warfare 2 | MP | [iw4x](https://iw4x.io) | ✅ | ✅ | ✅ |
| Modern Warfare 3 | MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| World at War | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops | SP/ZM/MP | [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops II | SP/ZM/MP | [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) + [Plutonium](https://plutonium.pw) | ✅ | ✅ | ✅ |
| Black Ops III | SP/MP/ZM | [CleanOps](https://github.com/notnightwolf/cleanopsT7) | ✅ | ✅ | ✅ |

All titles use controller and gyro through Steam Input. You choose your gyro mode during setup (ADS, Hold, or Toggle). Aim assist is not available for MW2 SP and MW3 SP. CoD4x is available as an alternative MW1 MP client during setup.

Supports Steam Deck (LCD and OLED), Steam Machine, Legion Go / Go S / Go 2, ROG Ally / Ally X, MSI Claw 8, and PC. SteamOS, Bazzite, and CachyOS supported.

---

## Before You Install

1. Install your games on Steam first. You do not need to launch them.
2. Have a stable internet connection ready.
3. Plutonium online play requires a [free account](https://forum.plutonium.pw/register). LCD users who only want offline play do not need one.

---

## Installation

1. Press the Steam button → **Power** → **Switch to Desktop**.
2. Open a browser and go to this GitHub page.
3. Download the **[DeckOps Nightly file](https://github.com/GalvarinoDev/DeckOps-Nightly/releases/download/v1/DeckOps-Nightly.desktop)**.
4. Right-click the file → **Properties** → **Permissions** → tick **"Is executable"** → OK.
5. Double-click it.
   - **First time:** DeckOps installs and launches automatically.
   - **Already installed:** A menu appears with Launch and Uninstall options.

DeckOps checks for updates on every launch. Updates download only the changed files. Your config, logs, and music are never overwritten.

---

## After Installation

Click Continue when installation finishes. DeckOps reopens Steam automatically. First launches take longer while Proton sets things up.

If Steam asks about cloud saves, choose **Keep Local**. If asked about safe mode or hardware changes, choose **No**.

- **MW1.** Use the main entry for SP and the DeckOps shortcut for MP. Select the "Player" profile on first SP launch. The MW1 MP launcher runs during install to download mod files. Close it when the download finishes.
- **MW1 MP (Non-Steam).** Launch MW1 MP twice on first install. The first launch fails. Relaunch and it works.
- **MW2 MP.** The first install takes a while if IW4x detects a downgrade is needed.
- **LCD Steam Deck.** Plutonium games may take a moment to launch during shader cache cleanup. Skip Vulkan shader compilation if prompted. Quit from the in-game menu for a faster exit.

---

## Gyro Controls

DeckOps installs a controller profile for every game. Choose your gyro mode during setup, or change it in **Settings > Controller Profiles > Re-apply Templates**. R5 is push-to-talk in all modes.

| Mode | How it works | Devices |
|---|---|---|
| **ADS** | Gyro activates when you aim down sights | Deck / Steam Controller |
| **Hold** | Gyro activates while L5 is held | Deck / Steam Controller |
| **Toggle** | L5 press on / L5 press off | Deck / Steam Controller |
| **On / Off** | Simple toggle | Legion Go, ROG Ally, MSI Claw 8, PC |

---

## Settings

| Option | What it does |
|---|---|
| Background Music | Turn on/off and adjust volume |
| Controller Profiles | Switch gyro mode and re-apply controller templates |
| Player Name | Change your in-game name for CoD4R, CoD4x, IW4x, and Plutonium offline |
| Shader Cache (LCD only) | Clear shader cache data for all set-up games |
| Check for Updates | Check for and apply DeckOps updates |
| Full Uninstall | Remove everything DeckOps installed (backs up saves first) |
| Reset DeckOps Config | Wipe config and run setup again |
| Links | Discord, Stable repo, and Nightly repo |

---

## Troubleshooting

https://discord.gg/bkSQeq5Azk

---

## Credits

DeckOps is an installer. This project would not exist without years of foundational work from these teams:

**[CoD4R](https://github.com/Divity)** - MW1 MP client (Call of Duty 4: Revived) by [k/divity](https://github.com/Divity). Native controller support, aim assist, server browser, and bot support. [Discord](https://discord.com/invite/uWAuFzru34) | 💰 [Ko-fi](https://ko-fi.com/divity)

**[CoD4x](https://cod4x.ovh)** - MW1 MP alternative client. [GitHub](https://github.com/callofduty4x)

**[IW3SP-MOD](https://gitea.com/JerryALT/iw3sp_mod)** - MW1 SP client by [JerryALT](https://gitea.com/JerryALT).

**[iw4x](https://iw4x.io)** - MW2 MP client. [GitHub](https://github.com/iw4x)

**[AlterWare](https://github.com/alterware)** - Ghosts (IW6-Mod), Advanced Warfare (S1-Mod), and Black Ops III (T7x) clients. All three were discontinued by the developer in September 2026.

**[CleanOps](https://github.com/notnightwolf/cleanopsT7)** - Black Ops III mod by [notnightwolf](https://github.com/notnightwolf).

**[T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release)** - Black Ops II SP client by [Rattpak](https://github.com/Rattpak).

**[Plutonium](https://plutonium.pw)** - MW3, WaW, BO1, and BO2 client. 💰 [Donate](https://forum.plutonium.pw/donate)

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
