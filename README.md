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

**LCD Online Play** · Plutonium online multiplayer now works on LCD Steam Decks. All seven Plutonium titles can connect to online servers from both LCD and OLED hardware. A [free Plutonium account](https://forum.plutonium.pw/register) is required. This is not ban evasion. DeckOps does not bypass or interfere with Plutonium's anti-cheat in any way, no fingerprinting is removed. We use the same methods they recommend the average Linux user to use during installation. This prevents it from triggering the false positive ban and you can enjoy Plutonium servers just like an OLED user would.

**Multi-Device Support** · DeckOps now runs on more than just Steam Deck. The setup flow includes a device picker with support for: Steam Machine, the Lenovo Legion Go, Go S, and Go 2, the ASUS ROG Ally, Ally X, and Xbox Ally X, the MSI Claw 8, and PCs. Each device gets resolution-tuned display configs and a controller template set matched to its hardware (paddle count, touchpad availability, etc.). Non-SteamOS devices on Bazzite or CachyOS are also supported and auto-route to the advanced install flow.

**Controller Templates** · DeckOps ships 44 templates covering every major controller type: Steam Controller 2 (Triton), PS5, PS5 Edge, PS4, Xbox 360, Xbox One, Xbox Elite, and generic. 28 universal templates are always installed. Only the Neptune variant matching your device is installed on top of those, keeping the template list clean. Steam Machine uses Triton templates as its primary controller with full gyro mode support.

**Hold and Toggle Gyro** · Steam Deck LCD and OLED now have four gyro modes: ADS, Hold, Toggle, and Off. Hold activates gyro while L5 is pressed. Toggle activates gyro on L5 press and deactivates on the next press. R5 remains push-to-talk in all modes. Other devices get On or Off. You can change your gyro mode anytime in Settings.

**Ghosts and Advanced Warfare** · Both titles supported via AlterWare (IW6-Mod and S1-Mod). Singleplayer and multiplayer for each game. The AlterWare launcher runs natively on Linux and downloads mod client files automatically during setup.

**Black Ops III** · Supported via CleanOps + T7x. CleanOps is a lightweight DLL mod that patches BO3 to protect against exploits and adds dedicated servers alongside Activision's official servers. T7x is an optional additional client with its own dedicated server list (~105 MB). T7X is offered as an opt-in during setup. Both clients can coexist in the same install. T7X creates a symlink farm in a sibling directory next to your BO3 install, keeping the Steam-managed directory completely clean.

**Black Ops II Singleplayer** · Supported via [T6SP-Mod](https://github.com/Rattpak/T6SP-Mod-Release) by Rattpak. DeckOps installs the mod client and deploys display settings automatically. Please be aware their mod is still in the Beta process, they've been gracious enough to let us use it despite it not being fully released on their github.

**Non-Steam Game Support** · Games from the Microsoft Store, retail CD copies, and other storefronts are supported. Place your game files in `~/Games` and select **Steam & Non-Steam** during setup. DeckOps scans for your games using multiplayer map fastfiles as sentinels to verify game identity, then handles shortcuts, artwork, Proton prefixes, mod clients, controller profiles, and display configs automatically.

**Offline LAN Launcher** · A dedicated Game Mode launcher for playing Plutonium games offline with bots. Shows installed games with mode buttons (MP, SP, Zombies), supports full gamepad navigation, and works on both LCD and OLED without a Plutonium account. The launcher is a PyInstaller exe that runs inside GE-Proton as a non-Steam shortcut.

**Player Name** · Set your in-game name during setup, pre-filled from your Steam display name. Used in CoD4x, IW4x, AlterWare (Ghosts, AW), T7X, and Plutonium offline LAN mode. Does not affect Plutonium online or CleanOps (uses Steam name). Change it anytime in Settings.

**Save Backup and Restore** · Player save data (configs, stats, custom classes) is backed up before uninstall and can be restored after reinstall. Backups are stored outside the DeckOps install directory at `~/.local/share/deckops/save_backup/` so they survive a full uninstall. When backups are detected after a fresh install, the Setup Complete screen offers a one-click restore.

**No More Protontricks** · All runtime dependencies are now copied directly from GE-Proton's built-in prefix. Proton prefixes use a shared DLL directory with symlinks to reduce disk usage from ~725MB per prefix to ~120MB. Faster installs, fewer failure points, no external tools.

**Menu Mods** · Custom DeckOps UI mods for BO2 Multiplayer, BO2 Zombies, and MW3 Multiplayer, installed automatically during setup.

**UI Overhaul** · The setup flow has been split into dedicated modules and rebuilt from scratch. New flow: OS > Device > Gyro > Name > Source. Consistent spacing, layout, and navigation across every screen.

---

## 🚧 WIP / Coming Soon

**Docked Mode / Decky Plugin** · Play on a TV or monitor with an external controller. A Decky Loader plugin to auto-switch display settings when you dock and undock. The plugin is feature-complete and pending docked hardware testing.

**InputPlumber dbus integration to autodetect your device and controller settings.**

**Add Games from My Games screen without re-running the full setup wizard.**

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

**Click Continue when installation finishes, DeckOps will reopen Steam automatically.** The first launch of each game may take a moment while Proton sets things up.

If Steam asks about cloud saves, choose **Keep Local**. If asked about launching in safe mode or changing your settings due to a hardware change, choose **No**.

- **MW1 and WaW** have separate DeckOps multiplayer shortcuts in your Steam library. Use the main game entry for singleplayer and the DeckOps shortcut for multiplayer. MW1 Singleplayer: on first launch, select the "Player" profile. This is the profile DeckOps created with your display settings.
- **First launch:** All games take longer to launch the first time. This is normal and they will be faster on subsequent launches. Plutonium games must be launched once before they can be used with the offline LAN launcher.
- **MW2 Multiplayer (Non-Steam):** IW4x needs to be launched twice on initial installation. The first launch will fail, this is normal. Launch it again and it will work.
- **Black Ops III:** CleanOps and T7X finish installing on their first run. For the best experience, do the first launch in Desktop Mode:
  1. If you installed T7X, launch it first. Once it loads, close it.
  2. Launch Black Ops III. CleanOps will patch the game and may slow the Deck temporarily. It will not launch after patching. This is normal.
  3. Press the blue Stop button in Steam, then relaunch to verify it works.
  4. After this, both work fine in Game Mode.

  If you only installed CleanOps, skip step 1.

- **LCD Steam Deck:** Plutonium games may take a moment to launch while a shader cache cleanup runs. If a game does not start right away, be patient or try again. If Steam tries to compile Vulkan shaders before launching, skip it. These are not used by LCD Plutonium games. Quit games from the in-game menu rather than the Steam overlay for a faster exit.

---

## 🎮 Gyro Controls

DeckOps installs a custom controller profile for every game. During setup you choose whether to enable gyro and which mode to use. You can change this anytime in **Settings > Controller Profiles > Re-apply Templates**.

**Steam Deck LCD and OLED** have four gyro modes:

| Scheme | How it works |
|---|---|
| **ADS** | Gyro activates when you aim down sights |
| **Hold** | Gyro activates while L5 is held |
| **Toggle** | Gyro activates on L5 press, deactivates on the next press |
| **Off** | Gyro disabled |

R5 is push-to-talk in all modes.

**Steam Machine** uses the Steam Controller 2 (Triton) template set with full Hold/Toggle support.

**Other devices** (Legion Go, ROG Ally, MSI Claw 8, PC) get On or Off. Legion Go devices use a dedicated Neptune Legion template with 4 paddle support. ROG Ally, Ally X, Xbox Ally X, and MSI Claw 8 use the 2-button Neptune template.

MW1 MP, MW2 SP, and MW3 SP handle gyro differently due to controller support added via Steam Input.

---

## 🛠️ My Games Screen

The My Games screen shows every supported game as a card with header art and a client badge. Each card has a **Configure** button that opens a dialog with the following options:

- **Mods** - open mod and user map folders (available for CoD4x, IW4x, Plutonium, AlterWare, and T7x)
- **Update** - re-download the mod client for a game already set up
- **Reinstall** - run the full setup again for a game

Games that are detected but not yet configured show a **Set Up** button instead. The Plutonium Offline card has a **Re-Add** button to re-add the offline launcher shortcut.

The header bar includes a **Guide** button with post-install tips and a **Settings** button.

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
