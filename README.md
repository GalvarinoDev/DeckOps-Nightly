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
| Black Ops III | SP/MP/ZM | [CleanOps](https://github.com/notnightwolf/cleanopsT7) + [T7x](https://github.com/Starter-Pack/T7x) | ✅ | ✅ | ✅ |

> All titles support controller and gyro via Steam Input. During setup, choose your gyro style: **Hold** (R5 held), **ADS** (gyro activates when you aim down sights), or **Toggle** (R5 press). Aim assist is unavailable for MW1 MP, MW2 SP, MW3 SP, and BO2 SP.

---

## 🆕 What's New in Nightly

**LCD Online Play** · Plutonium online multiplayer now works on LCD Steam Decks. All seven Plutonium titles can connect to online servers from both LCD and OLED hardware. A [free Plutonium account](https://forum.plutonium.pw/register) is required. This is not ban evasion. DeckOps does not bypass or interfere with Plutonium's anti-cheat in any way.

**Ghosts and Advanced Warfare** · Both titles supported via AlterWare (IW6-Mod and S1-Mod). Singleplayer and multiplayer for each game. The AlterWare launcher runs natively on Linux and downloads mod client files automatically during setup.

**Black Ops III** · Now supported via CleanOps + T7x. CleanOps is a lightweight DLL mod that patches BO3 to protect against exploits and adds dedicated servers alongside Activision's official servers. T7x is an optional additional client with its own dedicated server list (~105 MB). T7X is offered as an opt-in during setup. Both clients can coexist in the same install.

**Black Ops II Singleplayer** · Now supported via [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) by Rattpak. DeckOps installs the mod client and deploys display settings automatically. Please be aware their mod is still in the Beta process, they've been gracious enough to let us use it despite it not being fully released on their github.

**Non-Steam Game Support** · Games from the Microsoft Store, retail CD copies, and other storefronts are now supported. Place your game files in `~/Games` and select **Steam & Non-Steam** during setup. DeckOps scans for your games and handles shortcuts, artwork, Proton prefixes, mod clients, controller profiles, and display configs automatically.

**Player Name** · Set your in-game name during setup, pre-filled from your Steam display name. Used in CoD4x, IW4x, AlterWare (Ghosts, AW), T7X, and Plutonium offline LAN mode. Does not affect Plutonium online or CleanOps (uses Steam name). Change it anytime in Settings.

**No More Protontricks** · All runtime dependencies are now copied directly from GE-Proton's built-in prefix. Faster installs, fewer failure points, no external tools.

**Menu Mods** · Custom DeckOps UI mods for BO2 Multiplayer, BO2 Zombies, and MW3 Multiplayer, installed automatically during setup.

---

## 🚧 WIP / Coming Soon

**Offline LAN Launcher** · A dedicated Game Mode launcher for playing Plutonium games offline with bots. Shows installed games with mode buttons (MP, SP, Zombies), supports full gamepad navigation, and works on both LCD and OLED without a Plutonium account.

**Docked Mode / Decky Plugin** · Play on a TV or monitor with an external controller. A Decky Loader plugin to auto-switch display settings when you dock and undock.

---

## ⚠️ Before You Install

Install your games on Steam first, then install DeckOps. No need to launch any game beforehand.

Plutonium online play requires a [free account](https://forum.plutonium.pw/register) and works on both LCD and OLED Steam Decks. LCD users who only want to play offline do not need a Plutonium account. DeckOps automatically launches all Plutonium games in offline LAN mode on LCD when no account is configured.

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

## ⚠️ After Installation

**Click Continue when installation finishes, DeckOps will reopen Steam automatically.** The first launch of each game may take a moment while Proton sets things up.

If Steam asks about cloud saves, choose **Keep Local**. If asked about launching in safe mode or changing your settings due to a hardware change, choose **No**.

- **MW1 MP** requires two Steam launches to finish setup, then runs normally on the third.
- **First launch:** All games may take a while to launch the first time — this is normal. They will run fine after the initial launch.
- **Black Ops III:** CleanOps and T7X install on their first run, which takes a bit and may slow down the Steam Deck temporarily. Wiggle the analog sticks to keep the screen from turning off while you wait.

---

## 🎮 Gyro Controls

DeckOps installs a custom controller profile for every game. During setup you choose one of three gyro schemes, you can change this anytime in **Settings -> Controller Profiles -> Re-apply Templates**.

| Scheme | How it works |
|---|---|
| **Hold** | Gyro is active while R5 (right grip) is held down |
| **ADS** | Gyro activates when you aim down sights |
| **Toggle** | Press R5 once to turn gyro on, press again to turn it off |

MW1 MP, MW2 SP, and MW3 SP handle gyro differently due to controller support added via Steam Input.

---

## 🛠️ My Games Screen

The My Games screen shows every supported game as a card with header art and a client badge. Each card has a **Configure** button that opens a dialog with the following options:

- **Mods** — browse and install mods or user maps (available for CoD4x, IW4x, Plutonium, AlterWare, and T7x)
- **Update** — re-download the mod client for a game already set up
- **Reinstall** — run the full setup again for a game

Games that are detected but not yet configured show a **Set Up** button instead. The Plutonium Offline card has a **Re-Add** button to re-add the offline launcher shortcut.

The header bar includes a **Guide** button with post-install tips and a **Settings** button.

---

## ⚙️ Settings

| Option | What it does |
|---|---|
| Background Music | Toggle on/off and adjust volume |
| Controller Profiles | Switch gyro mode (Hold, Toggle, ADS) and re-apply controller templates to all games |
| Player Name | Change your in-game name for CoD4x, IW4x, AlterWare (Ghosts, AW), T7X, and Plutonium offline LAN mode |
| Shader Cache (LCD only) | Clear shader cache data for all set-up games |
| Links | Quick links to the Discord, Stable repo, and Nightly repo |
| Full Uninstall | Remove everything DeckOps installed |
| Reset DeckOps Config | Wipe DeckOps config and run setup again |

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
