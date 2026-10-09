/*
    DeckOps In-Game Create-a-Class Editor v1.0 (IW5 / MW3)
    =======================================================
    Server-side GSC script for Plutonium IW5 dedicated servers.
    Drop into: storage/iw5/scripts/deckops_cac.gsc

    Ported from IW4x MW2 CAC v2.0, menu input/hints updated to v2.1 — adapted for MW3 class system:
        - IW5 weapon codenames (iw5_ prefix)
        - Weapon Proficiencies (per weapon class)
        - Dual attachment support (2nd slot requires Attachments proficiency)
        - MW3 perks, equipment, tacticals, deathstreaks
        - Offline: no unlock gating, everything is available
        - Edits go into the "gamemode" loadout (player data writes drop the client on IW5 LAN)
        - Per-weapon attachment restrictions (isValidCombination)

    Controls:
        - Open: CHOOSE CLASS in the in-game menu (hub: Class Editor, Map / Mode, Bot Warfare)
        - Scroll Up: W / Dpad Up (+actionslot 1)
        - Scroll Down: S / Dpad Down (+actionslot 2)
        - Select: Jump (Space / A button), Reload (X button) or Use (F key)
        - Back: Stance (B button) or Aim (ADS / Left Trigger)

    Credits:
        - Divity (k) - Original in-game CAC concept and setPlayerData backend
        - EternalHabit/Antiga - Mapvote HUD pattern reference
        - DeckOps Community
*/

#include common_scripts\utility;
#include maps\mp\_utility;
#include maps\mp\gametypes\_hud_util;

init()
{
    precacheShader("gradient_center");
    precacheShader("white");
    precacheShader("line_horizontal_scorebar");
    precacheShader("black");

    buildWeaponData();
    buildPerkData();
    buildEquipmentData();
    buildProficiencyData();
    buildStreakData();
    buildNameLookup();

    level thread onPlayerConnect();
    level thread applyMatchOptions();
}

onPlayerConnect()
{
    for (;;)
    {
        level waittill("connected", player);
        if (!isDefined(player.pers["isBot"]) || player.pers["isBot"] == false)
        {
            player initCac();
            player thread watchForMenuOpen();
            player thread watchDeath();
            player thread watchSpawnLoadout();
        }
    }
}

// ============================================================
// DEATH WATCHER (close the menu if the player dies with it open)
// ============================================================

watchDeath()
{
    self endon("disconnect");
    for (;;)
    {
        self waittill("death");
        self cacCleanup();
    }
}

// Every menu function ends on death, so the HUD, freeze and open flag are released here too
cacCleanup()
{
    // only a menu that was open counts toward resuming the bots
    if (isDefined(self.cac_ui))
        self botsResume();
    if (isDefined(self.cac_huds))
        for (i = 0; i < self.cac_huds.size; i++)
            if (isDefined(self.cac_huds[i]))
                self.cac_huds[i] destroy();
    self.cac_huds = undefined;
    self.cac_ui = undefined;
    self freezeControlsWrapper(false);
    self setClientDvar("actionSlotsHide", "0");
    self.cac_open = false;
}

// ============================================================
// DATA TABLES
// ============================================================

buildWeaponData()
{
    level.cac = [];

    // --- Primary weapon categories ---
    level.cac["primary_cats"] = [];
    level.cac["primary_cats"][0] = "Assault Rifles";
    level.cac["primary_cats"][1] = "SMGs";
    level.cac["primary_cats"][2] = "LMGs";
    level.cac["primary_cats"][3] = "Sniper Rifles";
    level.cac["primary_cats"][4] = "Shotguns";
    level.cac["primary_cats"][5] = "Riot Shield";

    // --- Assault Rifles ---
    level.cac["ar"] = [];       level.cac["ar_name"] = [];
    level.cac["ar"][0] = "iw5_m4";        level.cac["ar_name"][0] = "M4A1";
    level.cac["ar"][1] = "iw5_m16";       level.cac["ar_name"][1] = "M16A4";
    level.cac["ar"][2] = "iw5_scar";      level.cac["ar_name"][2] = "SCAR-L";
    level.cac["ar"][3] = "iw5_cm901";     level.cac["ar_name"][3] = "CM901";
    level.cac["ar"][4] = "iw5_type95";    level.cac["ar_name"][4] = "Type 95";
    level.cac["ar"][5] = "iw5_g36c";      level.cac["ar_name"][5] = "G36C";
    level.cac["ar"][6] = "iw5_acr";       level.cac["ar_name"][6] = "ACR 6.8";
    level.cac["ar"][7] = "iw5_mk14";      level.cac["ar_name"][7] = "MK14";
    level.cac["ar"][8] = "iw5_ak47";      level.cac["ar_name"][8] = "AK-47";
    level.cac["ar"][9] = "iw5_fad";       level.cac["ar_name"][9] = "FAD";

    // --- SMGs ---
    level.cac["smg"] = [];      level.cac["smg_name"] = [];
    level.cac["smg"][0] = "iw5_mp5";      level.cac["smg_name"][0] = "MP5";
    level.cac["smg"][1] = "iw5_mp7";      level.cac["smg_name"][1] = "MP7";
    level.cac["smg"][2] = "iw5_ak74u";    level.cac["smg_name"][2] = "AK-74u";
    level.cac["smg"][3] = "iw5_p90";      level.cac["smg_name"][3] = "P90";
    level.cac["smg"][4] = "iw5_pp90m1";   level.cac["smg_name"][4] = "PP90M1";
    level.cac["smg"][5] = "iw5_ump45";    level.cac["smg_name"][5] = "UMP45";

    // --- LMGs ---
    level.cac["lmg"] = [];      level.cac["lmg_name"] = [];
    level.cac["lmg"][0] = "iw5_sa80";     level.cac["lmg_name"][0] = "L86 LSW";
    level.cac["lmg"][1] = "iw5_mg36";     level.cac["lmg_name"][1] = "MG36";
    level.cac["lmg"][2] = "iw5_pecheneg"; level.cac["lmg_name"][2] = "PKP Pecheneg";
    level.cac["lmg"][3] = "iw5_mk46";     level.cac["lmg_name"][3] = "MK46";
    level.cac["lmg"][4] = "iw5_m60";      level.cac["lmg_name"][4] = "M60E4";

    // --- Sniper Rifles ---
    level.cac["sniper"] = [];   level.cac["sniper_name"] = [];
    level.cac["sniper"][0] = "iw5_barrett";   level.cac["sniper_name"][0] = "Barrett .50cal";
    level.cac["sniper"][1] = "iw5_l96a1";     level.cac["sniper_name"][1] = "L118A";
    level.cac["sniper"][2] = "iw5_dragunov";  level.cac["sniper_name"][2] = "Dragunov";
    level.cac["sniper"][3] = "iw5_as50";      level.cac["sniper_name"][3] = "AS50";
    level.cac["sniper"][4] = "iw5_rsass";     level.cac["sniper_name"][4] = "RSASS";
    level.cac["sniper"][5] = "iw5_msr";       level.cac["sniper_name"][5] = "MSR";
    level.cac["sniper"][6] = "iw5_cheytac";   level.cac["sniper_name"][6] = "Intervention";

    // --- Shotguns ---
    level.cac["shotgun"] = [];  level.cac["shotgun_name"] = [];
    level.cac["shotgun"][0] = "iw5_usas12";    level.cac["shotgun_name"][0] = "USAS 12";
    level.cac["shotgun"][1] = "iw5_ksg";       level.cac["shotgun_name"][1] = "KSG 12";
    level.cac["shotgun"][2] = "iw5_spas12";    level.cac["shotgun_name"][2] = "SPAS-12";
    level.cac["shotgun"][3] = "iw5_aa12";      level.cac["shotgun_name"][3] = "AA-12";
    level.cac["shotgun"][4] = "iw5_striker";   level.cac["shotgun_name"][4] = "Striker";
    level.cac["shotgun"][5] = "iw5_1887";      level.cac["shotgun_name"][5] = "Model 1887";

    // --- Riot Shield ---
    level.cac["shield"] = [];   level.cac["shield_name"] = [];
    level.cac["shield"][0] = "riotshield";     level.cac["shield_name"][0] = "Riot Shield";

    // --- Secondary weapon categories ---
    level.cac["secondary_cats"] = [];
    level.cac["secondary_cats"][0] = "Machine Pistols";
    level.cac["secondary_cats"][1] = "Handguns";
    level.cac["secondary_cats"][2] = "Launchers";

    // --- Machine Pistols ---
    level.cac["machpistol"] = [];       level.cac["machpistol_name"] = [];
    level.cac["machpistol"][0] = "iw5_fmg9";      level.cac["machpistol_name"][0] = "FMG9";
    level.cac["machpistol"][1] = "iw5_mp9";        level.cac["machpistol_name"][1] = "MP9";
    level.cac["machpistol"][2] = "iw5_skorpion";   level.cac["machpistol_name"][2] = "Skorpion";
    level.cac["machpistol"][3] = "iw5_g18";        level.cac["machpistol_name"][3] = "G18";

    // --- Handguns ---
    level.cac["hg"] = [];       level.cac["hg_name"] = [];
    level.cac["hg"][0] = "iw5_usp45";         level.cac["hg_name"][0] = "USP .45";
    level.cac["hg"][1] = "iw5_p99";           level.cac["hg_name"][1] = "P99";
    level.cac["hg"][2] = "iw5_mp412";         level.cac["hg_name"][2] = "MP412";
    level.cac["hg"][3] = "iw5_44magnum";      level.cac["hg_name"][3] = ".44 Magnum";
    level.cac["hg"][4] = "iw5_deserteagle";   level.cac["hg_name"][4] = "Desert Eagle";
    level.cac["hg"][5] = "iw5_fnfiveseven";   level.cac["hg_name"][5] = "Five Seven";

    // --- Launchers ---
    level.cac["launcher"] = []; level.cac["launcher_name"] = [];
    level.cac["launcher"][0] = "iw5_smaw";     level.cac["launcher_name"][0] = "SMAW";
    level.cac["launcher"][1] = "javelin";      level.cac["launcher_name"][1] = "Javelin";
    level.cac["launcher"][2] = "stinger";      level.cac["launcher_name"][2] = "Stinger";
    level.cac["launcher"][3] = "rpg";          level.cac["launcher_name"][3] = "RPG-7";
    level.cac["launcher"][4] = "xm25";         level.cac["launcher_name"][4] = "XM25";

    // ========================================
    // Per-weapon-class attachment tables
    // ========================================

    // AR attachments
    level.cac["attach_ar"] = [];         level.cac["attach_ar_name"] = [];
    level.cac["attach_ar"][0] = "none";          level.cac["attach_ar_name"][0] = "No Attachment";
    level.cac["attach_ar"][1] = "reflex";        level.cac["attach_ar_name"][1] = "Red Dot Sight";
    level.cac["attach_ar"][2] = "eotech";        level.cac["attach_ar_name"][2] = "Holographic Sight";
    level.cac["attach_ar"][3] = "acog";          level.cac["attach_ar_name"][3] = "ACOG Scope";
    level.cac["attach_ar"][4] = "thermal";       level.cac["attach_ar_name"][4] = "Thermal Scope";
    level.cac["attach_ar"][5] = "hybrid";        level.cac["attach_ar_name"][5] = "Hybrid Sight";
    level.cac["attach_ar"][6] = "silencer";      level.cac["attach_ar_name"][6] = "Silencer";
    level.cac["attach_ar"][7] = "heartbeat";     level.cac["attach_ar_name"][7] = "Heartbeat Sensor";
    level.cac["attach_ar"][8] = "grip";          level.cac["attach_ar_name"][8] = "Grip";
    level.cac["attach_ar"][9] = "gl";            level.cac["attach_ar_name"][9] = "Grenade Launcher";
    level.cac["attach_ar"][10] = "shotgun";      level.cac["attach_ar_name"][10] = "Shotgun";
    level.cac["attach_ar"][11] = "xmags";        level.cac["attach_ar_name"][11] = "Extended Mags";

    // SMG attachments
    level.cac["attach_smg"] = [];        level.cac["attach_smg_name"] = [];
    level.cac["attach_smg"][0] = "none";         level.cac["attach_smg_name"][0] = "No Attachment";
    level.cac["attach_smg"][1] = "reflex";       level.cac["attach_smg_name"][1] = "Red Dot Sight";
    level.cac["attach_smg"][2] = "eotech";       level.cac["attach_smg_name"][2] = "Holographic Sight";
    level.cac["attach_smg"][3] = "acog";         level.cac["attach_smg_name"][3] = "ACOG Scope";
    level.cac["attach_smg"][4] = "thermal";      level.cac["attach_smg_name"][4] = "Thermal Scope";
    level.cac["attach_smg"][5] = "silencer";     level.cac["attach_smg_name"][5] = "Silencer";
    level.cac["attach_smg"][6] = "rof";          level.cac["attach_smg_name"][6] = "Rapid Fire";
    level.cac["attach_smg"][7] = "xmags";        level.cac["attach_smg_name"][7] = "Extended Mags";

    // LMG attachments
    level.cac["attach_lmg"] = [];        level.cac["attach_lmg_name"] = [];
    level.cac["attach_lmg"][0] = "none";         level.cac["attach_lmg_name"][0] = "No Attachment";
    level.cac["attach_lmg"][1] = "reflex";       level.cac["attach_lmg_name"][1] = "Red Dot Sight";
    level.cac["attach_lmg"][2] = "eotech";       level.cac["attach_lmg_name"][2] = "Holographic Sight";
    level.cac["attach_lmg"][3] = "acog";         level.cac["attach_lmg_name"][3] = "ACOG Scope";
    level.cac["attach_lmg"][4] = "thermal";      level.cac["attach_lmg_name"][4] = "Thermal Scope";
    level.cac["attach_lmg"][5] = "silencer";     level.cac["attach_lmg_name"][5] = "Silencer";
    level.cac["attach_lmg"][6] = "heartbeat";    level.cac["attach_lmg_name"][6] = "Heartbeat Sensor";
    level.cac["attach_lmg"][7] = "grip";         level.cac["attach_lmg_name"][7] = "Grip";
    level.cac["attach_lmg"][8] = "xmags";        level.cac["attach_lmg_name"][8] = "Extended Mags";

    // Sniper attachments
    level.cac["attach_sniper"] = [];     level.cac["attach_sniper_name"] = [];
    level.cac["attach_sniper"][0] = "none";          level.cac["attach_sniper_name"][0] = "No Attachment";
    level.cac["attach_sniper"][1] = "acog";          level.cac["attach_sniper_name"][1] = "ACOG Scope";
    level.cac["attach_sniper"][2] = "thermal";       level.cac["attach_sniper_name"][2] = "Thermal Scope";
    level.cac["attach_sniper"][3] = "vzscope";       level.cac["attach_sniper_name"][3] = "Variable Zoom";
    level.cac["attach_sniper"][4] = "silencer";      level.cac["attach_sniper_name"][4] = "Silencer";
    level.cac["attach_sniper"][5] = "heartbeat";     level.cac["attach_sniper_name"][5] = "Heartbeat Sensor";
    level.cac["attach_sniper"][6] = "xmags";         level.cac["attach_sniper_name"][6] = "Extended Mags";

    // Shotgun attachments
    level.cac["attach_shotgun"] = [];    level.cac["attach_shotgun_name"] = [];
    level.cac["attach_shotgun"][0] = "none";         level.cac["attach_shotgun_name"][0] = "No Attachment";
    level.cac["attach_shotgun"][1] = "reflex";       level.cac["attach_shotgun_name"][1] = "Red Dot Sight";
    level.cac["attach_shotgun"][2] = "eotech";       level.cac["attach_shotgun_name"][2] = "Holographic Sight";
    level.cac["attach_shotgun"][3] = "silencer";     level.cac["attach_shotgun_name"][3] = "Silencer";
    level.cac["attach_shotgun"][4] = "grip";         level.cac["attach_shotgun_name"][4] = "Grip";
    level.cac["attach_shotgun"][5] = "xmags";        level.cac["attach_shotgun_name"][5] = "Extended Mags";

    // Machine Pistol attachments
    level.cac["attach_machpistol"] = [];         level.cac["attach_machpistol_name"] = [];
    level.cac["attach_machpistol"][0] = "none";          level.cac["attach_machpistol_name"][0] = "No Attachment";
    level.cac["attach_machpistol"][1] = "reflex";        level.cac["attach_machpistol_name"][1] = "Red Dot Sight";
    level.cac["attach_machpistol"][2] = "eotech";        level.cac["attach_machpistol_name"][2] = "Holographic Sight";
    level.cac["attach_machpistol"][3] = "silencer";      level.cac["attach_machpistol_name"][3] = "Silencer";
    level.cac["attach_machpistol"][4] = "akimbo";        level.cac["attach_machpistol_name"][4] = "Akimbo";
    level.cac["attach_machpistol"][5] = "xmags";         level.cac["attach_machpistol_name"][5] = "Extended Mags";

    // Handgun attachments (USP, P99, Five Seven)
    level.cac["attach_hg"] = [];         level.cac["attach_hg_name"] = [];
    level.cac["attach_hg"][0] = "none";          level.cac["attach_hg_name"][0] = "No Attachment";
    level.cac["attach_hg"][1] = "silencer";      level.cac["attach_hg_name"][1] = "Silencer";
    level.cac["attach_hg"][2] = "akimbo";        level.cac["attach_hg_name"][2] = "Akimbo";
    level.cac["attach_hg"][3] = "tactical";      level.cac["attach_hg_name"][3] = "Tactical Knife";
    level.cac["attach_hg"][4] = "xmags";         level.cac["attach_hg_name"][4] = "Extended Mags";

    // Handgun attachments (Magnum, Desert Eagle, MP412 — no silencer, no xmags)
    level.cac["attach_hg2"] = [];        level.cac["attach_hg2_name"] = [];
    level.cac["attach_hg2"][0] = "none";         level.cac["attach_hg2_name"][0] = "No Attachment";
    level.cac["attach_hg2"][1] = "akimbo";       level.cac["attach_hg2_name"][1] = "Akimbo";
    level.cac["attach_hg2"][2] = "tactical";     level.cac["attach_hg2_name"][2] = "Tactical Knife";

    // ========================================
    // Weapon -> attachment table mapping
    // ========================================
    level.cac["wep_attach_type"] = [];
    // ARs
    level.cac["wep_attach_type"]["iw5_m4"] = "ar";
    level.cac["wep_attach_type"]["iw5_m16"] = "ar";
    level.cac["wep_attach_type"]["iw5_scar"] = "ar";
    level.cac["wep_attach_type"]["iw5_cm901"] = "ar";
    level.cac["wep_attach_type"]["iw5_type95"] = "ar";
    level.cac["wep_attach_type"]["iw5_g36c"] = "ar";
    level.cac["wep_attach_type"]["iw5_acr"] = "ar";
    level.cac["wep_attach_type"]["iw5_mk14"] = "ar";
    level.cac["wep_attach_type"]["iw5_ak47"] = "ar";
    level.cac["wep_attach_type"]["iw5_fad"] = "ar";
    // SMGs
    level.cac["wep_attach_type"]["iw5_mp5"] = "smg";
    level.cac["wep_attach_type"]["iw5_mp7"] = "smg";
    level.cac["wep_attach_type"]["iw5_ak74u"] = "smg";
    level.cac["wep_attach_type"]["iw5_p90"] = "smg";
    level.cac["wep_attach_type"]["iw5_pp90m1"] = "smg";
    level.cac["wep_attach_type"]["iw5_ump45"] = "smg";
    // LMGs
    level.cac["wep_attach_type"]["iw5_sa80"] = "lmg";
    level.cac["wep_attach_type"]["iw5_mg36"] = "lmg";
    level.cac["wep_attach_type"]["iw5_pecheneg"] = "lmg";
    level.cac["wep_attach_type"]["iw5_mk46"] = "lmg";
    level.cac["wep_attach_type"]["iw5_m60"] = "lmg";
    // Snipers
    level.cac["wep_attach_type"]["iw5_barrett"] = "sniper";
    level.cac["wep_attach_type"]["iw5_l96a1"] = "sniper";
    level.cac["wep_attach_type"]["iw5_dragunov"] = "sniper";
    level.cac["wep_attach_type"]["iw5_as50"] = "sniper";
    level.cac["wep_attach_type"]["iw5_rsass"] = "sniper";
    level.cac["wep_attach_type"]["iw5_msr"] = "sniper";
    level.cac["wep_attach_type"]["iw5_cheytac"] = "sniper";
    // Shotguns
    level.cac["wep_attach_type"]["iw5_usas12"] = "shotgun";
    level.cac["wep_attach_type"]["iw5_ksg"] = "shotgun";
    level.cac["wep_attach_type"]["iw5_spas12"] = "shotgun";
    level.cac["wep_attach_type"]["iw5_aa12"] = "shotgun";
    level.cac["wep_attach_type"]["iw5_striker"] = "shotgun";
    level.cac["wep_attach_type"]["iw5_1887"] = "shotgun";
    // Machine Pistols
    level.cac["wep_attach_type"]["iw5_fmg9"] = "machpistol";
    level.cac["wep_attach_type"]["iw5_mp9"] = "machpistol";
    level.cac["wep_attach_type"]["iw5_skorpion"] = "machpistol";
    level.cac["wep_attach_type"]["iw5_g18"] = "machpistol";
    // Handguns (full)
    level.cac["wep_attach_type"]["iw5_usp45"] = "hg";
    level.cac["wep_attach_type"]["iw5_p99"] = "hg";
    level.cac["wep_attach_type"]["iw5_fnfiveseven"] = "hg";
    // Handguns (limited)
    level.cac["wep_attach_type"]["iw5_44magnum"] = "hg2";
    level.cac["wep_attach_type"]["iw5_deserteagle"] = "hg2";
    level.cac["wep_attach_type"]["iw5_mp412"] = "hg2";
    // No attachments
    level.cac["wep_attach_type"]["riotshield"] = "none";
    level.cac["wep_attach_type"]["iw5_smaw"] = "none";
    level.cac["wep_attach_type"]["javelin"] = "none";
    level.cac["wep_attach_type"]["stinger"] = "none";
    level.cac["wep_attach_type"]["rpg"] = "none";
    level.cac["wep_attach_type"]["xm25"] = "none";

    // ========================================
    // Per-weapon attachment restrictions
    // (from isValidCombination in _class.gsc)
    // ========================================
    level.cac["wep_attach_restrict"] = [];
    // M60 and Pecheneg cannot use heartbeat
    level.cac["wep_attach_restrict"]["iw5_m60"] = [];
    level.cac["wep_attach_restrict"]["iw5_m60"][0] = "heartbeat";
    level.cac["wep_attach_restrict"]["iw5_pecheneg"] = [];
    level.cac["wep_attach_restrict"]["iw5_pecheneg"][0] = "heartbeat";
    // .44 Magnum, Desert Eagle, MP412 cannot use silencer or xmags
    // (already handled by hg2 attach table which excludes them)
}

buildPerkData()
{
    level.cac["perk1"] = [];    level.cac["perk1_name"] = [];
    level.cac["perk1"][0] = "specialty_fastreload";    level.cac["perk1_name"][0] = "Sleight of Hand";
    level.cac["perk1"][1] = "specialty_longersprint";  level.cac["perk1_name"][1] = "Extreme Conditioning";
    level.cac["perk1"][2] = "specialty_scavenger";     level.cac["perk1_name"][2] = "Scavenger";
    level.cac["perk1"][3] = "specialty_blindeye";      level.cac["perk1_name"][3] = "Blind Eye";
    level.cac["perk1"][4] = "specialty_paint";         level.cac["perk1_name"][4] = "Recon";

    level.cac["perk2"] = [];    level.cac["perk2_name"] = [];
    level.cac["perk2"][0] = "specialty_quickdraw";       level.cac["perk2_name"][0] = "Quickdraw";
    level.cac["perk2"][1] = "specialty_hardline";        level.cac["perk2_name"][1] = "Hardline";
    level.cac["perk2"][2] = "specialty_coldblooded";     level.cac["perk2_name"][2] = "Assassin";
    level.cac["perk2"][3] = "specialty_twoprimaries";    level.cac["perk2_name"][3] = "Overkill";
    level.cac["perk2"][4] = "_specialty_blastshield";    level.cac["perk2_name"][4] = "Blast Shield";

    level.cac["perk3"] = [];    level.cac["perk3_name"] = [];
    level.cac["perk3"][0] = "specialty_stalker";           level.cac["perk3_name"][0] = "Stalker";
    level.cac["perk3"][1] = "specialty_bulletaccuracy";    level.cac["perk3_name"][1] = "Steady Aim";
    level.cac["perk3"][2] = "specialty_detectexplosive";   level.cac["perk3_name"][2] = "SitRep";
    level.cac["perk3"][3] = "specialty_autospot";          level.cac["perk3_name"][3] = "Marksman";
    level.cac["perk3"][4] = "specialty_quieter";           level.cac["perk3_name"][4] = "Dead Silence";

    level.cac["deathstreak"] = [];    level.cac["deathstreak_name"] = [];
    level.cac["deathstreak"][0] = "specialty_null";              level.cac["deathstreak_name"][0] = "None";
    level.cac["deathstreak"][1] = "specialty_juiced";            level.cac["deathstreak_name"][1] = "Juiced";
    level.cac["deathstreak"][2] = "specialty_finalstand";        level.cac["deathstreak_name"][2] = "Final Stand";
    level.cac["deathstreak"][3] = "specialty_grenadepulldeath";  level.cac["deathstreak_name"][3] = "Martyrdom";
    level.cac["deathstreak"][4] = "specialty_revenge";           level.cac["deathstreak_name"][4] = "Revenge";
    level.cac["deathstreak"][5] = "specialty_stopping_power";    level.cac["deathstreak_name"][5] = "Hollow Points";
    level.cac["deathstreak"][6] = "specialty_c4death";           level.cac["deathstreak_name"][6] = "Dead Man's Hand";
}

buildEquipmentData()
{
    level.cac["equip"] = [];    level.cac["equip_name"] = [];
    level.cac["equip"][0] = "frag_grenade_mp";       level.cac["equip_name"][0] = "Frag Grenade";
    level.cac["equip"][1] = "semtex_mp";             level.cac["equip_name"][1] = "Semtex";
    level.cac["equip"][2] = "throwingknife_mp";      level.cac["equip_name"][2] = "Throwing Knife";
    level.cac["equip"][3] = "claymore_mp";           level.cac["equip_name"][3] = "Claymore";
    level.cac["equip"][4] = "c4_mp";                 level.cac["equip_name"][4] = "C4";
    level.cac["equip"][5] = "bouncingbetty_mp";      level.cac["equip_name"][5] = "Bouncing Betty";

    level.cac["tactical"] = [];  level.cac["tactical_name"] = [];
    level.cac["tactical"][0] = "flash_grenade_mp";           level.cac["tactical_name"][0] = "Flash Grenade";
    level.cac["tactical"][1] = "concussion_grenade_mp";      level.cac["tactical_name"][1] = "Stun Grenade";
    level.cac["tactical"][2] = "smoke_grenade_mp";           level.cac["tactical_name"][2] = "Smoke Grenade";
    level.cac["tactical"][3] = "trophy_mp";                  level.cac["tactical_name"][3] = "Trophy System";
    level.cac["tactical"][4] = "specialty_portable_radar";   level.cac["tactical_name"][4] = "Portable Radar";
    level.cac["tactical"][5] = "emp_grenade_mp";             level.cac["tactical_name"][5] = "EMP Grenade";
    level.cac["tactical"][6] = "specialty_scrambler";        level.cac["tactical_name"][6] = "Scrambler";
    level.cac["tactical"][7] = "specialty_tacticalinsertion"; level.cac["tactical_name"][7] = "Tactical Insertion";
}

buildProficiencyData()
{
    // Weapon proficiencies vary by weapon class
    // Stored per weapon class, selected based on primary/secondary weapon

    // Assault Rifle proficiencies
    level.cac["prof_ar"] = [];           level.cac["prof_ar_name"] = [];
    level.cac["prof_ar"][0] = "specialty_bling";              level.cac["prof_ar_name"][0] = "Attachments";
    level.cac["prof_ar"][1] = "specialty_bulletpenetration";  level.cac["prof_ar_name"][1] = "Impact";
    level.cac["prof_ar"][2] = "specialty_marksman";           level.cac["prof_ar_name"][2] = "Kick";
    level.cac["prof_ar"][3] = "specialty_sharp_focus";        level.cac["prof_ar_name"][3] = "Focus";
    level.cac["prof_ar"][4] = "specialty_holdbreathwhileads"; level.cac["prof_ar_name"][4] = "Breath";
    level.cac["prof_ar"][5] = "specialty_reducedsway";        level.cac["prof_ar_name"][5] = "Stability";

    // SMG proficiencies
    level.cac["prof_smg"] = [];          level.cac["prof_smg_name"] = [];
    level.cac["prof_smg"][0] = "specialty_bling";         level.cac["prof_smg_name"][0] = "Attachments";
    level.cac["prof_smg"][1] = "specialty_marksman";      level.cac["prof_smg_name"][1] = "Kick";
    level.cac["prof_smg"][2] = "specialty_sharp_focus";   level.cac["prof_smg_name"][2] = "Focus";
    level.cac["prof_smg"][3] = "specialty_reducedsway";   level.cac["prof_smg_name"][3] = "Stability";
    level.cac["prof_smg"][4] = "specialty_longerrange";   level.cac["prof_smg_name"][4] = "Range";
    level.cac["prof_smg"][5] = "specialty_fastermelee";   level.cac["prof_smg_name"][5] = "Melee";

    // LMG proficiencies
    level.cac["prof_lmg"] = [];          level.cac["prof_lmg_name"] = [];
    level.cac["prof_lmg"][0] = "specialty_bling";              level.cac["prof_lmg_name"][0] = "Attachments";
    level.cac["prof_lmg"][1] = "specialty_bulletpenetration";  level.cac["prof_lmg_name"][1] = "Impact";
    level.cac["prof_lmg"][2] = "specialty_marksman";           level.cac["prof_lmg_name"][2] = "Kick";
    level.cac["prof_lmg"][3] = "specialty_sharp_focus";        level.cac["prof_lmg_name"][3] = "Focus";
    level.cac["prof_lmg"][4] = "specialty_reducedsway";        level.cac["prof_lmg_name"][4] = "Stability";
    level.cac["prof_lmg"][5] = "specialty_lightweight";        level.cac["prof_lmg_name"][5] = "Speed";

    // Sniper proficiencies
    level.cac["prof_sniper"] = [];       level.cac["prof_sniper_name"] = [];
    level.cac["prof_sniper"][0] = "specialty_bling";              level.cac["prof_sniper_name"][0] = "Attachments";
    level.cac["prof_sniper"][1] = "specialty_bulletpenetration";  level.cac["prof_sniper_name"][1] = "Impact";
    level.cac["prof_sniper"][2] = "specialty_marksman";           level.cac["prof_sniper_name"][2] = "Kick";
    level.cac["prof_sniper"][3] = "specialty_sharp_focus";        level.cac["prof_sniper_name"][3] = "Focus";
    level.cac["prof_sniper"][4] = "specialty_reducedsway";        level.cac["prof_sniper_name"][4] = "Stability";
    level.cac["prof_sniper"][5] = "specialty_lightweight";        level.cac["prof_sniper_name"][5] = "Speed";

    // Shotgun proficiencies
    level.cac["prof_shotgun"] = [];      level.cac["prof_shotgun_name"] = [];
    level.cac["prof_shotgun"][0] = "specialty_bling";         level.cac["prof_shotgun_name"][0] = "Attachments";
    level.cac["prof_shotgun"][1] = "specialty_marksman";      level.cac["prof_shotgun_name"][1] = "Kick";
    level.cac["prof_shotgun"][2] = "specialty_sharp_focus";   level.cac["prof_shotgun_name"][2] = "Focus";
    level.cac["prof_shotgun"][3] = "specialty_longerrange";   level.cac["prof_shotgun_name"][3] = "Range";
    level.cac["prof_shotgun"][4] = "specialty_fastermelee";   level.cac["prof_shotgun_name"][4] = "Melee";
    level.cac["prof_shotgun"][5] = "specialty_moredamage";    level.cac["prof_shotgun_name"][5] = "Damage";

    // Riot Shield proficiencies
    level.cac["prof_shield"] = [];       level.cac["prof_shield_name"] = [];
    level.cac["prof_shield"][0] = "specialty_fastermelee";   level.cac["prof_shield_name"][0] = "Melee";
    level.cac["prof_shield"][1] = "specialty_lightweight";   level.cac["prof_shield_name"][1] = "Speed";

    // Weapon class -> proficiency table mapping
    level.cac["wep_prof_type"] = [];
    level.cac["wep_prof_type"]["iw5_m4"] = "ar";
    level.cac["wep_prof_type"]["iw5_m16"] = "ar";
    level.cac["wep_prof_type"]["iw5_scar"] = "ar";
    level.cac["wep_prof_type"]["iw5_cm901"] = "ar";
    level.cac["wep_prof_type"]["iw5_type95"] = "ar";
    level.cac["wep_prof_type"]["iw5_g36c"] = "ar";
    level.cac["wep_prof_type"]["iw5_acr"] = "ar";
    level.cac["wep_prof_type"]["iw5_mk14"] = "ar";
    level.cac["wep_prof_type"]["iw5_ak47"] = "ar";
    level.cac["wep_prof_type"]["iw5_fad"] = "ar";
    level.cac["wep_prof_type"]["iw5_mp5"] = "smg";
    level.cac["wep_prof_type"]["iw5_mp7"] = "smg";
    level.cac["wep_prof_type"]["iw5_ak74u"] = "smg";
    level.cac["wep_prof_type"]["iw5_p90"] = "smg";
    level.cac["wep_prof_type"]["iw5_pp90m1"] = "smg";
    level.cac["wep_prof_type"]["iw5_ump45"] = "smg";
    level.cac["wep_prof_type"]["iw5_sa80"] = "lmg";
    level.cac["wep_prof_type"]["iw5_mg36"] = "lmg";
    level.cac["wep_prof_type"]["iw5_pecheneg"] = "lmg";
    level.cac["wep_prof_type"]["iw5_mk46"] = "lmg";
    level.cac["wep_prof_type"]["iw5_m60"] = "lmg";
    level.cac["wep_prof_type"]["iw5_barrett"] = "sniper";
    level.cac["wep_prof_type"]["iw5_l96a1"] = "sniper";
    level.cac["wep_prof_type"]["iw5_dragunov"] = "sniper";
    level.cac["wep_prof_type"]["iw5_as50"] = "sniper";
    level.cac["wep_prof_type"]["iw5_rsass"] = "sniper";
    level.cac["wep_prof_type"]["iw5_msr"] = "sniper";
    level.cac["wep_prof_type"]["iw5_cheytac"] = "sniper";
    level.cac["wep_prof_type"]["iw5_usas12"] = "shotgun";
    level.cac["wep_prof_type"]["iw5_ksg"] = "shotgun";
    level.cac["wep_prof_type"]["iw5_spas12"] = "shotgun";
    level.cac["wep_prof_type"]["iw5_aa12"] = "shotgun";
    level.cac["wep_prof_type"]["iw5_striker"] = "shotgun";
    level.cac["wep_prof_type"]["iw5_1887"] = "shotgun";
    level.cac["wep_prof_type"]["riotshield"] = "shield";
}

// ============================================================
// UNLOCK FILTER HELPERS
// ============================================================

// Edits live in self.pers["gamemodeLoadout"], which _class.gsc gives for class "gamemode"
// without unlock checks. A server dvar per guid keeps it across map changes.
cacKeys()
{
    k = [];
    k[0] = "loadoutPrimary";              k[1] = "loadoutPrimaryAttachment";    k[2] = "loadoutPrimaryAttachment2";
    k[3] = "loadoutPrimaryBuff";          k[4] = "loadoutSecondary";            k[5] = "loadoutSecondaryAttachment";
    k[6] = "loadoutSecondaryAttachment2"; k[7] = "loadoutSecondaryBuff";        k[8] = "loadoutEquipment";
    k[9] = "loadoutOffhand";              k[10] = "loadoutPerk1";               k[11] = "loadoutPerk2";
    k[12] = "loadoutPerk3";               k[13] = "loadoutDeathstreak";
    k[14] = "loadoutStreakType";          k[15] = "loadoutKillstreak1";         k[16] = "loadoutKillstreak2";
    k[17] = "loadoutKillstreak3";
    return k;
}

initCac()
{
    l = [];
    l["loadoutPrimary"] = "iw5_m4";           l["loadoutPrimaryAttachment"] = "none";   l["loadoutPrimaryAttachment2"] = "none";
    l["loadoutPrimaryBuff"] = "specialty_null"; l["loadoutPrimaryCamo"] = "none";       l["loadoutPrimaryReticle"] = "none";
    l["loadoutSecondary"] = "iw5_usp45";      l["loadoutSecondaryAttachment"] = "none"; l["loadoutSecondaryAttachment2"] = "none";
    l["loadoutSecondaryBuff"] = "specialty_null"; l["loadoutSecondaryCamo"] = "none";   l["loadoutSecondaryReticle"] = "none";
    l["loadoutEquipment"] = "frag_grenade_mp"; l["loadoutOffhand"] = "flash_grenade_mp";
    l["loadoutPerk1"] = "specialty_longersprint"; l["loadoutPerk2"] = "specialty_quickdraw"; l["loadoutPerk3"] = "specialty_bulletaccuracy";
    l["loadoutDeathstreak"] = "specialty_null"; l["loadoutJuggernaut"] = false;
    l["loadoutStreakType"] = "streaktype_assault";
    l["loadoutKillstreak1"] = "uav"; l["loadoutKillstreak2"] = "predator_missile"; l["loadoutKillstreak3"] = "helicopter";

    saved = getDvar("dcac_" + self.guid);
    if (saved != "")
    {
        vals = strTok(saved, ",");
        keys = cacKeys();
        if (vals.size == keys.size)
            for (i = 0; i < keys.size; i++)
                l[keys[i]] = vals[i];
    }
    self.pers["gamemodeLoadout"] = l;
}

cacSet(key, value)
{
    self.pers["gamemodeLoadout"][key] = value;
    keys = cacKeys();
    str = "";
    for (i = 0; i < keys.size; i++)
    {
        if (i > 0) str += ",";
        str += self.pers["gamemodeLoadout"][keys[i]];
    }
    setDvar("dcac_" + self.guid, str);
}

cacGet(key)
{
    return self.pers["gamemodeLoadout"][key];
}

wKey(slot, field)
{
    base = "loadoutPrimary";
    if (slot == 1) base = "loadoutSecondary";
    if (field == "attachment0") return base + "Attachment";
    if (field == "attachment1") return base + "Attachment2";
    if (field == "buff") return base + "Buff";
    return base;
}

perkKey(slot)
{
    if (slot == 0) return "loadoutEquipment";
    if (slot == 6) return "loadoutOffhand";
    return "loadoutPerk" + slot;
}

getUnlockedItems(listKey, nameKey)
{
    items = [];
    items["keys"] = [];
    items["names"] = [];
    count = 0;

    for (i = 0; i < level.cac[listKey].size; i++)
    {
        {
            items["keys"][count] = level.cac[listKey][i];
            items["names"][count] = level.cac[nameKey][i];
            count++;
        }
    }

    return items;
}

getUnlockedAttachments(weapon, attachListKey, attachNameKey)
{
    items = [];
    items["keys"] = [];
    items["names"] = [];
    count = 0;

    for (i = 0; i < level.cac[attachListKey].size; i++)
    {
        attach = level.cac[attachListKey][i];

        // Always include "none"
        if (attach == "none")
        {
            items["keys"][count] = attach;
            items["names"][count] = level.cac[attachNameKey][i];
            count++;
            continue;
        }

        // Check per-weapon restrictions
        if (isDefined(level.cac["wep_attach_restrict"][weapon]))
        {
            restricted = false;
            for (r = 0; r < level.cac["wep_attach_restrict"][weapon].size; r++)
            {
                if (level.cac["wep_attach_restrict"][weapon][r] == attach)
                {
                    restricted = true;
                    break;
                }
            }
            if (restricted)
                continue;
        }

        {
            items["keys"][count] = attach;
            items["names"][count] = level.cac[attachNameKey][i];
            count++;
        }
    }

    return items;
}

// Second attachment: not the same one, and not a second sight or underbarrel
// (buildWeaponName in _class.gsc only maps one rail optic)
attachGroup(a)
{
    if (a == "acog" || a == "eotech" || a == "hybrid" || a == "reflex" || a == "thermal" || a == "vzscope")
        return "sight";
    if (a == "gl" || a == "shotgun" || a == "grip")
        return "under";
    return a;
}

dropClashingAttachments(list, first)
{
    out = [];
    out["keys"] = [];
    out["names"] = [];
    for (i = 0; i < list["keys"].size; i++)
    {
        a = list["keys"][i];
        if (a != "none" && (a == first || attachGroup(a) == attachGroup(first)))
            continue;
        out["keys"][out["keys"].size] = a;
        out["names"][out["names"].size] = list["names"][i];
    }
    return out;
}

getUnlockedProficiencies(weapon, profListKey, profNameKey)
{
    items = [];
    items["keys"] = [];
    items["names"] = [];
    count = 0;

    for (i = 0; i < level.cac[profListKey].size; i++)
    {
        prof = level.cac[profListKey][i];
        {
            items["keys"][count] = prof;
            items["names"][count] = level.cac[profNameKey][i];
            count++;
        }
    }

    return items;
}

// ============================================================
// MENU OPEN/CLOSE WATCHER
// ============================================================

watchForMenuOpen()
{
    self endon("disconnect");

    self.cac_open = false;

    // Scroll up: W, Dpad Up, mouse wheel up
    self notifyOnPlayerCommand("cac_up", "+forward");
    self notifyOnPlayerCommand("cac_up", "+actionslot 1");
    self notifyOnPlayerCommand("cac_up", "+weapnext");
    // Scroll down: S, Dpad Down, mouse wheel down
    self notifyOnPlayerCommand("cac_down", "+back");
    self notifyOnPlayerCommand("cac_down", "+actionslot 2");
    self notifyOnPlayerCommand("cac_down", "+weapdown");
    // Select: Jump, Reload, Use/F
    self notifyOnPlayerCommand("cac_select", "+gostand");
    self notifyOnPlayerCommand("cac_select", "+usereload");
    self notifyOnPlayerCommand("cac_select", "+activate");
    // Back: B (+stance on the gamepad), ADS (L2 / right mouse)
    self notifyOnPlayerCommand("cac_back", "+stance");
    self notifyOnPlayerCommand("cac_back", "+speed_throw");
    self notifyOnPlayerCommand("cac_back", "+toggleads_throw");

    self thread watchChooseClass();

    for (;;)
    {
        self waittill("cac_toggle");

        if (self.sessionstate != "playing")
            continue;

        if (!self.cac_open)
        {
            self.cac_open = true;
            self thread openHubMenu();
        }
    }
}

// CHOOSE CLASS in the in-game menu sends ("class", "changeclass_marines"/"changeclass_opfor").
// The stock script opens the class list for it; close that and open the editor instead.
watchChooseClass()
{
    self endon("disconnect");
    for (;;)
    {
        self waittill("menuresponse", menu, response);
        if (menu == "class" && isSubStr(response, "changeclass"))
            self thread openEditorFromChooseClass();
        // A class picked from the stock list opened by the hub replaces the DeckOps loadout.
        // The forced pick on joining a map also comes from "changeclass", so only the hub's counts.
        if (menu == "changeclass" && isDefined(self.cac_choosing) && self.cac_choosing)
        {
            self.cac_choosing = false;
            if (response != "back")
                setDvar("dcac_on_" + self.guid, "0");
        }
    }
}

openEditorFromChooseClass()
{
    self endon("disconnect");
    wait 0.05;
    self closepopupmenu();
    self closeingamemenu();
    if (!self.cac_open)
        self notify("cac_toggle");
}

// With nothing saved yet, start the editor from the class in use instead of the defaults.
// Reads only: giveLoadout records the base loadout on the player, _class.gsc's getters cover custom classes.
cacSeedFromCurrent()
{
    if (getDvar("dcac_" + self.guid) != "" || !isDefined(self.loadoutPrimary) || cacModeOwnsLoadout())
        return;

    l = self.pers["gamemodeLoadout"];
    l["loadoutPrimary"] = self.loadoutPrimary;
    l["loadoutSecondary"] = self.loadoutSecondary;
    l["loadoutPrimaryBuff"] = self.loadoutPrimaryBuff;
    l["loadoutSecondaryBuff"] = self.loadoutSecondaryBuff;
    l["loadoutPerk1"] = self.loadoutPerk1;
    l["loadoutPerk2"] = self.loadoutPerk2;
    l["loadoutPerk3"] = self.loadoutPerk3;
    l["loadoutEquipment"] = self.loadoutPerkEquipment;

    if (isSubStr(self.class, "custom") && isDefined(self.class_num))
    {
        n = self.class_num;
        l["loadoutPrimaryAttachment"] = self maps\mp\gametypes\_class::cac_getWeaponAttachment(n, 0);
        l["loadoutPrimaryAttachment2"] = self maps\mp\gametypes\_class::cac_getWeaponAttachmentTwo(n, 0);
        l["loadoutSecondaryAttachment"] = self maps\mp\gametypes\_class::cac_getWeaponAttachment(n, 1);
        l["loadoutSecondaryAttachment2"] = self maps\mp\gametypes\_class::cac_getWeaponAttachmentTwo(n, 1);
        l["loadoutOffhand"] = self maps\mp\gametypes\_class::cac_getOffhand(n);
        l["loadoutDeathstreak"] = self maps\mp\gametypes\_class::cac_getDeathstreak(n);
    }

    if (isDefined(self.streakType) && isDefined(self.killStreaks))
    {
        l["loadoutStreakType"] = "streaktype_" + self.streakType;
        k = 1;
        foreach (ks in self.killStreaks)
        {
            if (k <= 3) l["loadoutKillstreak" + k] = ks;
            k++;
        }
    }

    self.pers["gamemodeLoadout"] = l;
    // saves the seeded set, so this runs once per session
    self cacSet("loadoutPrimary", l["loadoutPrimary"]);
}

// ============================================================
// HUB MENU (opened by CHOOSE CLASS)
// ============================================================

openHubMenu()
{
    self endon("disconnect");
    self endon("death");

    self cacSeedFromCurrent();

    items = [];
    items[0] = "Class Editor";
    items[1] = "Choose Class";
    items[2] = "Map / Mode";
    items[3] = "Bot Warfare";

    d = [];
    d[0] = "Build your loadout: weapons, perks, streaks.";
    d[1] = "Use one of MW3's own classes instead.";
    d[2] = "Change the mode, the map and the match limits.";
    d[3] = "How many bots, how tough, and how they play.";
    self.cac_descs = d;
    result = self showMenu("DECKOPS SETTINGS", items, "");
    switch (result)
    {
        case 0:
        case 1:
            if (cacModeOwnsLoadout())
            {
                self iPrintLnBold("^1This mode uses its own loadouts");
                self thread openHubMenu();
            }
            else if (result == 0) self thread openCACMenu();
            else self thread openStockClassList();
            break;
        case 2: self thread openMatchMenu(); break;
        case 3: self thread openBotMenu(); break;
        default: self cacCleanup(); break;
    }
}

// Hub "Choose Class": MW3's own class list, so default and saved custom classes stay available
openStockClassList()
{
    self endon("disconnect");
    self cacCleanup();
    self.cac_choosing = true;
    self openpopupmenu("changeclass");
}

// ============================================================
// MAP / MODE (ends the match and loads the pick through the rotation)
// ============================================================

// Time and score limits come from the DSR into scr_<gametype>_*, which the match logic keeps
// reading, so they change live. The DSR resets them on every map, so they are re-applied.
applyMatchOptions()
{
    level endon("game_ended");
    wait 1;
    gt = level.gameType;
    if (getDvar("dcac_base_score_" + gt) == "")
        setDvar("dcac_base_score_" + gt, "" + getDvarInt("scr_" + gt + "_scorelimit"));
    if (getDvar("dcac_opt_timelimit") != "")
        setDvar("scr_" + gt + "_timelimit", getDvar("dcac_opt_timelimit"));
    if (getDvar("dcac_opt_score") != "")
        setDvar("scr_" + gt + "_scorelimit", "" + int(getDvarInt("dcac_base_score_" + gt) * getDvarFloat("dcac_opt_score")));
}

// One setup screen: rows show the pending choice, Start Match applies them together
matchModes()
{
    m = [];
    m["dsr"] = strTok("TDM_default,FFA_default,DOM_default,KC_default,SD_default,HQ_default,DD_default,CTF_default,INF_default", ",");
    m["gt"] = strTok("war,dm,dom,conf,sd,koth,dd,ctf,infect", ",");
    m["name"] = strTok("Team Deathmatch,Free-for-All,Domination,Kill Confirmed,Search and Destroy,Headquarters,Demolition,Capture the Flag,Infected", ",");
    return m;
}

matchMaps()
{
    m = [];
    m["key"] = strTok("mp_alpha,mp_bootleg,mp_bravo,mp_carbon,mp_dome,mp_exchange,mp_hardhat,mp_interchange,mp_lambeth,mp_mogadishu,mp_paris,mp_plaza2,mp_radar,mp_seatown,mp_underground,mp_village", ",");
    m["name"] = strTok("Lockdown,Bootleg,Mission,Carbon,Dome,Downturn,Hardhat,Interchange,Fallen,Bakaara,Resistance,Arkaden,Outpost,Seatown,Underground,Village", ",");
    return m;
}

indexOf(list, value)
{
    for (i = 0; i < list.size; i++)
        if (list[i] == value)
            return i;
    return 0;
}

openMatchMenu(index)
{
    self endon("disconnect");
    self endon("death");

    if (isDefined(index)) self.cac_startIndex = index;

    modes = matchModes();
    maps = matchMaps();
    if (!isDefined(self.mm_mode))
    {
        // start from what is running now
        self.mm_mode = indexOf(modes["gt"], level.gameType);
        self.mm_map = indexOf(maps["key"], getDvar("mapname"));
        self.mm_time = getDvar("dcac_opt_timelimit");
        if (self.mm_time == "") self.mm_time = "" + getDvarInt("scr_" + level.gameType + "_timelimit");
        self.mm_score = getDvar("dcac_opt_score");
        if (self.mm_score == "") self.mm_score = "1";
    }

    items = [];
    items[0] = "Mode: " + modes["name"][self.mm_mode];
    items[1] = "Map: " + maps["name"][self.mm_map];
    if (self.mm_time == "0") items[2] = "Time Limit: Unlimited";
    else items[2] = "Time Limit: " + self.mm_time + " min";
    items[3] = "Score Limit: " + scoreName(self.mm_score);
    items[4] = "Start Match";

    d = [];
    d[0] = "Which game mode to play next.";
    d[1] = "Which map to play next.";
    d[2] = "How long a match lasts.";
    d[3] = "How many points win the match.";
    d[4] = "Load mode and map. Limits alone apply instantly.";
    self.cac_descs = d;
    result = self showMenu("MAP / MODE", items, "");
    switch (result)
    {
        case 0: self thread pickFromList("Mode", modes["name"], "mm_mode", 0); break;
        case 1: self thread pickFromList("Map", maps["name"], "mm_map", 0); break;
        case 2: self thread pickTimeLimit(); break;
        case 3: self thread pickScoreLimit(); break;
        case 4: self thread startMatch(); break;
        default:
            self.mm_mode = undefined;
            self thread openHubMenu();
            break;
    }
}

// Generic paged picker that stores the chosen index in self.<field> and returns to the setup screen
pickFromList(title, names, field, page)
{
    self endon("disconnect");
    self endon("death");

    first = page * 9;
    rows = [];
    for (i = first; i < names.size && i < first + 9; i++)
        rows[rows.size] = names[i];
    more = first + 9 < names.size;
    if (more) rows[rows.size] = "More";
    else if (page > 0) rows[rows.size] = "Back to Start";

    result = self showMenu(title, rows, "");
    if (result == -1) { self thread openMatchMenu(); return; }
    if (first + result >= names.size || result >= 9)
    {
        if (more) self thread pickFromList(title, names, field, page + 1);
        else self thread pickFromList(title, names, field, 0);
        return;
    }
    if (field == "mm_mode") { self.mm_mode = first + result; self thread openMatchMenu(0); }
    else { self.mm_map = first + result; self thread openMatchMenu(1); }
}

scoreName(mult)
{
    if (mult == "0") return "Unlimited";
    if (mult == "0.5") return "Half";
    if (mult == "2") return "Double";
    return "Default";
}

pickTimeLimit()
{
    self endon("disconnect");
    self endon("death");

    vals = strTok("0,5,10,15,20,30", ",");
    names = strTok("Unlimited,5 min,10 min,15 min,20 min,30 min", ",");
    result = self showMenu("Time Limit", names, "");
    if (result != -1) self.mm_time = vals[result];
    self thread openMatchMenu(2);
}

pickScoreLimit()
{
    self endon("disconnect");
    self endon("death");

    // relative to the mode's DSR default, captured before any override
    mult = strTok("0,0.5,1,2", ",");
    names = strTok("Unlimited,Half,Default,Double", ",");
    result = self showMenu("Score Limit", names, "");
    if (result != -1) self.mm_score = mult[result];
    self thread openMatchMenu(3);
}

startMatch()
{
    self endon("disconnect");

    modes = matchModes();
    maps = matchMaps();
    setDvar("dcac_opt_timelimit", self.mm_time);
    setDvar("dcac_opt_score", self.mm_score);
    sameMatch = modes["gt"][self.mm_mode] == level.gameType && maps["key"][self.mm_map] == getDvar("mapname");
    self cacCleanup();

    if (sameMatch)
    {
        // only the limits changed: apply live, no restart
        level thread applyMatchOptions();
        self iPrintLnBold("^2Match settings applied");
        self.mm_mode = undefined;
        return;
    }

    rot = "dsr " + modes["dsr"][self.mm_mode] + " map " + maps["key"][self.mm_map];
    self.mm_mode = undefined;
    setDvar("sv_maprotation", rot);
    setDvar("sv_maprotationcurrent", rot);
    iPrintLnBold("^2Loading ^7" + maps["name"][self.mm_map] + " ^2- ^7" + modes["name"][indexOf(modes["dsr"], strTok(rot, " ")[1])]);
    wait 2;
    exitLevel(false);
}

// ============================================================
// BOT WARFARE (Bot Warfare reads these dvars live)
// ============================================================

openBotMenu(index)
{
    self endon("disconnect");
    self endon("death");

    if (isDefined(index)) self.cac_startIndex = index;

    items = [];
    items[0] = "Bot Count: " + getDvarInt("bots_manage_fill");
    items[1] = "Difficulty: " + botSkillName(getDvarInt("bots_skill"));
    if (getDvar("bots_team") == "autoassign" || getDvar("bots_team") == "") items[2] = "Bot Team: Balanced";
    else items[2] = "Bot Team: All Enemies";
    items[3] = "Play Objective: " + onOff(botSetting("bots_play_obj"));
    items[4] = "Camping: " + onOff(botSetting("bots_play_camp"));
    items[5] = "Killstreaks: " + onOff(botSetting("bots_play_killstreak"));
    items[6] = "Take Care Packages: " + onOff(botSetting("bots_play_take_carepackages"));
    items[7] = "Jump & Dropshot: " + onOff(botSetting("bots_play_jumpdrop"));
    if (getDvarInt("bots_loadout_allow_op")) items[8] = "Bot Classes: Anything Goes";
    else items[8] = "Bot Classes: Sensible";
    // Bot Warfare reads bots_main_chat per message as a chattiness multiplier
    c = getDvarFloat("bots_main_chat");
    if (c <= 0) items[9] = "Bot Chat: Off";
    else if (c < 2) items[9] = "Bot Chat: Normal";
    else items[9] = "Bot Chat: Chatty";

    d = [];
    d[0] = "How many bots are in the match (0 to 12).";
    d[1] = "How well bots aim and react. Mixed = all levels.";
    d[2] = "Balanced: bots on both sides. All Enemies: vs you.";
    d[3] = "Bots go for flags, bombs and capture points.";
    d[4] = "Bots sometimes hold a spot and wait for you.";
    d[5] = "Bots call in their own killstreaks.";
    d[6] = "Bots run to and grab care packages.";
    d[7] = "Bots jump and drop prone during gunfights.";
    d[8] = "Sensible: normal classes. Anything Goes: OP too.";
    d[9] = "Bots type in chat. Chatty means they talk more.";
    self.cac_descs = d;
    result = self showMenu("BOT WARFARE", items, "");
    switch (result)
    {
        case 0: self thread pickBotCount(); break;
        case 1: self thread pickBotSkill(); break;
        case 2:
            if (getDvar("bots_team") == "autoassign" || getDvar("bots_team") == "")
            {
                // every bot on the team opposite the player
                if (self.team == "axis") setDvar("bots_team", "allies");
                else setDvar("bots_team", "axis");
                setDvar("bots_team_force", "1");
            }
            else
            {
                setDvar("bots_team", "autoassign");
                setDvar("bots_team_force", "0");
            }
            self thread openBotMenu(2);
            break;
        case 3: botToggle("bots_play_obj"); self thread openBotMenu(3); break;
        case 4: botToggle("bots_play_camp"); self thread openBotMenu(4); break;
        case 5: botToggle("bots_play_killstreak"); self thread openBotMenu(5); break;
        case 6: botToggle("bots_play_take_carepackages"); self thread openBotMenu(6); break;
        case 7: botToggle("bots_play_jumpdrop"); self thread openBotMenu(7); break;
        case 8:
            if (getDvarInt("bots_loadout_allow_op"))
            {
                setDvar("bots_loadout_allow_op", "0");
                setDvar("bots_loadout_reasonable", "1");
            }
            else
            {
                setDvar("bots_loadout_allow_op", "1");
                setDvar("bots_loadout_reasonable", "0");
            }
            self thread openBotMenu(8);
            break;
        case 9:
            c = getDvarFloat("bots_main_chat");
            if (c <= 0) setDvar("bots_main_chat", "1");
            else if (c < 2) setDvar("bots_main_chat", "3");
            else setDvar("bots_main_chat", "0");
            self thread openBotMenu(9);
            break;
        default: self thread openHubMenu(); break;
    }
}

onOff(v)
{
    if (v) return "On";
    return "Off";
}

// While the menu is open botsPause holds some bots_play_* at 0 and restores them on close,
// so read and change the value it will restore, not the live one
botSetting(dvar)
{
    if (isDefined(level.dcac_botplay) && isDefined(level.dcac_botplay[dvar]))
        return int(level.dcac_botplay[dvar]);
    return getDvarInt(dvar);
}

botToggle(dvar)
{
    if (botSetting(dvar)) v = "0";
    else v = "1";
    if (isDefined(level.dcac_botplay) && isDefined(level.dcac_botplay[dvar]))
        level.dcac_botplay[dvar] = v;
    else
        setDvar(dvar, v);
}

pickBotCount()
{
    self endon("disconnect");
    self endon("death");

    // sv_maxclients is 13 in the LAN config: 12 bots + the player
    counts = strTok("0,2,4,6,8,10,12", ",");
    result = self showMenu("Bot Count", counts, "");
    if (result != -1)
        setDvar("bots_manage_fill", counts[result]);
    self thread openBotMenu(0);
}

pickBotSkill()
{
    self endon("disconnect");
    self endon("death");

    skills = strTok("0,1,3,5,7", ",");
    names = [];
    for (i = 0; i < skills.size; i++)
        names[i] = botSkillName(int(skills[i]));
    result = self showMenu("Difficulty", names, "");
    if (result != -1)
        setDvar("bots_skill", skills[result]);
    self thread openBotMenu(1);
}

botSkillName(n)
{
    if (n == 0) return "Mixed";
    if (n <= 2) return "Easy";
    if (n <= 4) return "Normal";
    if (n <= 6) return "Hard";
    return "Veteran";
}

// ============================================================
// MAIN MENU
// ============================================================

openCACMenu()
{
    self endon("disconnect");
    self endon("death");


    items = [];
    items[0] = "Primary Weapon";
    items[1] = "Primary Proficiency";
    items[2] = "Secondary Weapon";
    items[3] = "Perk 1 (Blue)";
    items[4] = "Perk 2 (Red)";
    items[5] = "Perk 3 (Yellow)";
    items[6] = "Equipment";
    items[7] = "Deathstreak";
    items[8] = "Strike Package";
    items[9] = "Apply Loadout";

    result = self showMenu("CLASS EDITOR", items, "");

    if (result == -1) { self thread openHubMenu(); return; }


    switch (result)
    {
        case 0: self thread pickPrimaryCategory(0); break;
        case 1: self thread pickProficiency(0); break;
        case 2: self thread pickSecondaryCategory(); break;
        case 3: self thread pickPerk(1); break;
        case 4: self thread pickPerk(2); break;
        case 5: self thread pickPerk(3); break;
        case 6: self thread pickEquipmentMenu(); break;
        case 7: self thread pickDeathstreak(); break;
        case 8: self thread pickStreakType(); break;
        case 9: self thread applyLoadout(); break;
    }
}

// ============================================================
// PRIMARY WEAPON FLOW
// ============================================================

pickPrimaryCategory(slot)
{
    if (!isDefined(slot)) slot = 0;

    self endon("disconnect");
    self endon("death");

    items = [];
    for (i = 0; i < level.cac["primary_cats"].size; i++)
        items[i] = level.cac["primary_cats"][i];

    title = "Primary - Category";
    if (slot == 1) title = "Overkill - Category";
    result = self showMenu(title, items, "");
    if (result == -1) { self thread openCACMenu(); return; }

    switch (result)
    {
        case 0: self thread pickWeaponFromList("ar", "ar_name", slot); break;
        case 1: self thread pickWeaponFromList("smg", "smg_name", slot); break;
        case 2: self thread pickWeaponFromList("lmg", "lmg_name", slot); break;
        case 3: self thread pickWeaponFromList("sniper", "sniper_name", slot); break;
        case 4: self thread pickWeaponFromList("shotgun", "shotgun_name", slot); break;
        case 5:
            if (true)
            {
                self cacSet(wKey(slot, "weapon"), "riotshield");
                self cacSet(wKey(slot, "attachment" + 0), "none");
                self cacSet(wKey(slot, "attachment" + 1), "none");
                self cacSet(wKey(slot, "buff"), "specialty_null");
                self iPrintLnBold("^2Weapon set: ^7Riot Shield");
            }
            else
                self iPrintLnBold("^1Riot Shield not unlocked yet");
            self thread openCACMenu();
            break;
    }
}

pickWeaponFromList(listKey, nameKey, weaponSlot)
{
    self endon("disconnect");
    self endon("death");

    unlocked = self getUnlockedItems(listKey, nameKey);

    if (unlocked["names"].size == 0)
    {
        self iPrintLnBold("^1No weapons unlocked in this category");
        if (weaponSlot == 0) self thread pickPrimaryCategory(0);
        else self thread pickSecondaryCategory();
        return;
    }

    title = "Pick Weapon";
    if (weaponSlot == 1) title = "Pick Secondary";

    result = self showMenu(title, unlocked["names"], "");
    if (result == -1)
    {
        if (weaponSlot == 0) self thread pickPrimaryCategory(0);
        else self thread pickSecondaryCategory();
        return;
    }

    weapon = unlocked["keys"][result];

    self cacSet(wKey(weaponSlot, "weapon"), weapon);
    self cacSet(wKey(weaponSlot, "attachment" + 0), "none");
    self cacSet(wKey(weaponSlot, "attachment" + 1), "none");
    self cacSet(wKey(weaponSlot, "buff"), "specialty_null");
    self iPrintLnBold("^2Weapon set: ^7" + unlocked["names"][result]);

    self thread pickAttachment(weapon, weaponSlot, 0);
}

// ============================================================
// SECONDARY WEAPON FLOW
// ============================================================

pickSecondaryCategory()
{
    self endon("disconnect");
    self endon("death");

    // Overkill: the secondary slot takes a primary weapon instead
    if (self cacGet("loadoutPerk2") == "specialty_twoprimaries")
    {
        self thread pickPrimaryCategory(1);
        return;
    }

    items = [];
    for (i = 0; i < level.cac["secondary_cats"].size; i++)
        items[i] = level.cac["secondary_cats"][i];

    result = self showMenu("Secondary - Category", items, "");
    if (result == -1) { self thread openCACMenu(); return; }

    switch (result)
    {
        case 0: self thread pickWeaponFromList("machpistol", "machpistol_name", 1); break;
        case 1: self thread pickWeaponFromList("hg", "hg_name", 1); break;
        case 2: self thread pickWeaponFromList("launcher", "launcher_name", 1); break;
    }
}

// ============================================================
// ATTACHMENT PICKER (per-weapon, unlock-gated)
// ============================================================

// Valid attachments per weapon come from the game's own mp/statsTable.csv (columns 11+), the same
// source as MW3's Create-a-Class and Bot Warfare. Codes are class-specific (silencer02 on pistols,
// silencer03 on shotguns, m320/gp25 launchers); generic codes build weapons that don't exist.
getAttachmentsForGun(gun)
{
    row = tableLookupRowNum("mp/statsTable.csv", 4, gun);
    atts = [];
    if (row < 0)
        return atts;
    for (h = 0; h < 10; h++)
    {
        a = tableLookupByRow("mp/statsTable.csv", row, h + 11);
        if (a == "")
            break;
        atts[atts.size] = a;
    }
    return atts;
}

// Pair rules from the game's mp/attachmentCombos.csv
isValidAttachmentCombo(att1, att2)
{
    if (att1 == "none" || att2 == "none")
        return true;
    if (att1 == att2)
        return false;
    col = tableLookupRowNum("mp/attachmentCombos.csv", 0, att1);
    return tableLookup("mp/attachmentCombos.csv", 0, att2, col) != "no";
}

gunHasAttachment(gun, att)
{
    atts = getAttachmentsForGun(gun);
    for (i = 0; i < atts.size; i++)
        if (atts[i] == att)
            return true;
    return false;
}

pickAttachment(weapon, weaponSlot, attachSlot, page)
{
    self endon("disconnect");
    self endon("death");

    if (!isDefined(page)) page = 0;

    first = self cacGet(wKey(weaponSlot, "attachment0"));
    atts = getAttachmentsForGun(weapon);
    keys = [];
    names = [];
    keys[0] = "none";
    names[0] = "No Attachment";
    for (i = 0; i < atts.size; i++)
    {
        if (attachSlot == 1 && !isValidAttachmentCombo(first, atts[i]))
            continue;
        keys[keys.size] = atts[i];
        names[names.size] = cacName(atts[i]);
    }

    // riot shield, launchers: nothing to pick
    if (keys.size <= 1)
    {
        self thread openCACMenu();
        return;
    }

    // 10 rows: 9 choices + More / Back to Start
    start = page * 9;
    rows = [];
    for (i = start; i < keys.size && i < start + 9; i++)
        rows[rows.size] = names[i];
    more = start + 9 < keys.size;
    if (more) rows[rows.size] = "More";
    else if (page > 0) rows[rows.size] = "Back to Start";

    result = self showMenu("Attachment " + (attachSlot + 1), rows, "");
    if (result == -1)
    {
        self thread openCACMenu();
        return;
    }
    if (start + result >= keys.size || result >= 9)
    {
        if (more) self thread pickAttachment(weapon, weaponSlot, attachSlot, page + 1);
        else self thread pickAttachment(weapon, weaponSlot, attachSlot, 0);
        return;
    }

    attach = keys[start + result];
    self cacSet(wKey(weaponSlot, "attachment" + attachSlot), attach);
    if (attachSlot == 0 && attach == "none")
        self cacSet(wKey(weaponSlot, "attachment1"), "none");
    // a new first attachment can clash with the second one
    if (attachSlot == 0 && !isValidAttachmentCombo(attach, self cacGet(wKey(weaponSlot, "attachment1"))))
        self cacSet(wKey(weaponSlot, "attachment1"), "none");

    // Attachments proficiency on the primary allows a second attachment
    if (attachSlot == 0 && attach != "none" && weaponSlot == 0 && self cacGet(wKey(0, "buff")) == "specialty_bling")
        self thread pickAttachment(weapon, weaponSlot, 1, 0);
    else
        self thread openCACMenu();
}

// ============================================================
// PROFICIENCY PICKER (per-weapon-class, unlock-gated)
// ============================================================

pickProficiency(weaponSlot)
{
    self endon("disconnect");
    self endon("death");

    weapon = self cacGet(wKey(weaponSlot, "weapon"));

    if (!isDefined(level.cac["wep_prof_type"][weapon]))
    {
        self iPrintLnBold("^1No proficiencies for this weapon");
        self thread openCACMenu();
        return;
    }

    profType = level.cac["wep_prof_type"][weapon];
    profListKey = "prof_" + profType;
    profNameKey = "prof_" + profType + "_name";

    unlocked = self getUnlockedProficiencies(weapon, profListKey, profNameKey);

    if (unlocked["names"].size == 0)
    {
        self iPrintLnBold("^1No proficiencies unlocked");
        self thread openCACMenu();
        return;
    }

    result = self showMenu("Proficiency", unlocked["names"], "");
    if (result == -1) { self thread openCACMenu(); return; }

    prof = unlocked["keys"][result];
    self cacSet(wKey(weaponSlot, "buff"), prof);
    self iPrintLnBold("^2Proficiency set: ^7" + unlocked["names"][result]);

    // Attachments proficiency unlocks a second attachment: offer it right away
    if (prof == "specialty_bling")
    {
        self thread pickAttachment(weapon, weaponSlot, 1);
        return;
    }
    self cacSet(wKey(weaponSlot, "attachment" + 1), "none");

    self thread openCACMenu();
}

// ============================================================
// PERK PICKER (unlock-gated)
// ============================================================

pickPerk(perkSlot)
{
    self endon("disconnect");
    self endon("death");

    listKey = "perk" + perkSlot;
    nameKey = "perk" + perkSlot + "_name";

    unlocked = self getUnlockedItems(listKey, nameKey);

    if (unlocked["names"].size == 0)
    {
        self iPrintLnBold("^1No perks unlocked in this slot");
        self thread openCACMenu();
        return;
    }

    slotNames = [];
    slotNames[1] = "Perk 1 (Blue)";
    slotNames[2] = "Perk 2 (Red)";
    slotNames[3] = "Perk 3 (Yellow)";

    result = self showMenu(slotNames[perkSlot], unlocked["names"], "");
    if (result == -1) { self thread openCACMenu(); return; }

    perk = unlocked["keys"][result];
    self cacSet(perkKey(perkSlot), perk);

    // Overkill: if selected, secondary buff needs to be valid
    // If deselected, clear secondary buff
    if (perkSlot == 2)
    {
        if (perk != "specialty_twoprimaries")
        {
            self cacSet(wKey(1, "buff"), "specialty_null");
            // dropping Overkill: a primary in the secondary slot goes back to a pistol
            if (isPrimaryWeapon(self cacGet("loadoutSecondary")))
            {
                self cacSet(wKey(1, "weapon"), "iw5_usp45");
                self cacSet(wKey(1, "attachment0"), "none");
                self cacSet(wKey(1, "attachment1"), "none");
            }
        }
    }

    self iPrintLnBold("^2Perk " + perkSlot + " set: ^7" + unlocked["names"][result]);
    self thread openCACMenu();
}

// ============================================================
// EQUIPMENT, TACTICAL, DEATHSTREAK
// ============================================================

pickEquipmentMenu()
{
    self endon("disconnect");
    self endon("death");

    items = [];
    items[0] = "Lethal";
    items[1] = "Tactical";
    result = self showMenu("Equipment", items, "");
    switch (result)
    {
        case 0: self thread pickEquipment(); break;
        case 1: self thread pickTactical(); break;
        default: self thread openCACMenu(); break;
    }
}

pickEquipment()
{
    self endon("disconnect");
    self endon("death");

    unlocked = self getUnlockedItems("equip", "equip_name");

    if (unlocked["names"].size == 0)
    {
        self iPrintLnBold("^1No equipment unlocked");
        self thread openCACMenu();
        return;
    }

    result = self showMenu("Equipment", unlocked["names"], "");
    if (result == -1) { self thread pickEquipmentMenu(); return; }

    self cacSet(perkKey(0), unlocked["keys"][result]);
    self iPrintLnBold("^2Equipment set: ^7" + unlocked["names"][result]);
    self thread pickEquipmentMenu();
}

pickTactical()
{
    self endon("disconnect");
    self endon("death");

    // Tacticals are always unlocked
    items = [];
    for (i = 0; i < level.cac["tactical"].size; i++)
        items[i] = level.cac["tactical_name"][i];

    result = self showMenu("Tactical", items, "");
    if (result == -1) { self thread pickEquipmentMenu(); return; }

    self cacSet(perkKey(6), level.cac["tactical"][result]);
    self iPrintLnBold("^2Tactical set: ^7" + level.cac["tactical_name"][result]);
    self thread pickEquipmentMenu();
}

pickDeathstreak()
{
    self endon("disconnect");
    self endon("death");

    // Deathstreaks — filter by unlock
    unlocked = self getUnlockedItems("deathstreak", "deathstreak_name");

    if (unlocked["names"].size == 0)
    {
        self iPrintLnBold("^1No deathstreaks unlocked");
        self thread openCACMenu();
        return;
    }

    result = self showMenu("Deathstreak", unlocked["names"], "");
    if (result == -1) { self thread openCACMenu(); return; }

    self cacSet("loadoutDeathstreak", unlocked["keys"][result]);
    self iPrintLnBold("^2Deathstreak set: ^7" + unlocked["names"][result]);
    self thread openCACMenu();
}

isPrimaryWeapon(w)
{
    if (w == "riotshield")
        return true;
    lists = strTok("ar,smg,lmg,sniper,shotgun", ",");
    for (l = 0; l < lists.size; l++)
        for (i = 0; i < level.cac[lists[l]].size; i++)
            if (level.cac[lists[l]][i] == w)
                return true;
    return false;
}

// ============================================================
// STRIKE PACKAGE
// ============================================================

pickStreakType()
{
    self endon("disconnect");
    self endon("death");

    result = self showMenu("Strike Package", level.cac["streaktypes_name"], "");
    if (result == -1) { self thread openCACMenu(); return; }

    self cacSet("loadoutStreakType", level.cac["streaktypes"][result]);
    self cacSet("loadoutKillstreak1", "none");
    self cacSet("loadoutKillstreak2", "none");
    self cacSet("loadoutKillstreak3", "none");
    self thread pickStreak(1);
}

// Streaks are stored by kill cost (setKillstreaks in _class.gsc), so two with the same cost
// would overwrite each other; Specialist costs are the slot (2/4/6) instead.
pickStreak(n)
{
    self endon("disconnect");
    self endon("death");

    type = getSubStr(self cacGet("loadoutStreakType"), 11);
    list = level.cac["ks_" + type];
    names = level.cac["ks_" + type + "_name"];

    keys = [];
    items = [];
    for (i = 0; i < list.size; i++)
    {
        ks = list[i];
        taken = false;
        for (k = 1; k < n; k++)
        {
            other = self cacGet("loadoutKillstreak" + k);
            if (other == ks)
                taken = true;
            else if (type != "specialist" && self maps\mp\killstreaks\_killstreaks::getStreakCost(other) == self maps\mp\killstreaks\_killstreaks::getStreakCost(ks))
                taken = true;
        }
        if (taken)
            continue;
        keys[keys.size] = ks;
        if (type == "specialist")
            items[items.size] = names[i] + " (" + (n * 2) + ")";
        else
            items[items.size] = names[i] + " (" + self maps\mp\killstreaks\_killstreaks::getStreakCost(ks) + ")";
    }

    // more than 10 choices: page with the last row
    self thread pickStreakPage(n, keys, items, 0);
}

pickStreakPage(n, keys, items, page)
{
    self endon("disconnect");
    self endon("death");

    first = page * 9;
    rows = [];
    for (i = first; i < items.size && i < first + 9; i++)
        rows[rows.size] = items[i];
    more = first + 9 < items.size;
    if (more) rows[rows.size] = "More";
    else if (page > 0) rows[rows.size] = "Back to Start";

    result = self showMenu("Killstreak " + n, rows, "");
    if (result == -1) { self thread pickStreakType(); return; }
    if (first + result >= items.size || result >= 9)
    {
        if (more) self thread pickStreakPage(n, keys, items, page + 1);
        else self thread pickStreakPage(n, keys, items, 0);
        return;
    }

    self cacSet("loadoutKillstreak" + n, keys[first + result]);
    if (n < 3) self thread pickStreak(n + 1);
    else self thread openCACMenu();
}

// Infected, Gun Game, One in the Chamber and the Juggernaut modes hand out their own loadouts
cacModeOwnsLoadout()
{
    switch (level.gameType)
    {
        case "infect":
        case "gun":
        case "oic":
        case "jugg":
        case "tjugg":
            return true;
    }
    return false;
}

// The gamemode class skips MW3's checks, so anything invalid falls back here instead of an empty hand
cacSanitize()
{
    p = self cacGet("loadoutPrimary");
    if (!maps\mp\gametypes\_class::isValidPrimary(p, false))
    {
        self cacSet("loadoutPrimary", "iw5_m4");
        p = "iw5_m4";
    }
    sec = self cacGet("loadoutSecondary");
    if (sec != "none" && !maps\mp\gametypes\_class::isValidSecondary(sec, self cacGet("loadoutPerk2"), self cacGet("loadoutPerk3"), false))
        self cacSet("loadoutSecondary", "iw5_usp45");

    slots = strTok("loadoutPrimary,loadoutSecondary", ",");
    for (s = 0; s < slots.size; s++)
    {
        w = self cacGet(slots[s]);
        a = strTok(slots[s] + "Attachment," + slots[s] + "Attachment2", ",");
        if (!isValidAttachmentCombo(self cacGet(a[0]), self cacGet(a[1])))
            self cacSet(a[1], "none");
        for (i = 0; i < a.size; i++)
        {
            att = self cacGet(a[i]);
            if (att != "none" && (!gunHasAttachment(w, att) || !maps\mp\gametypes\_class::isValidCombination(w, att)))
                self cacSet(a[i], "none");
        }
    }
}

// ============================================================
// APPLY LOADOUT (Divity's class swap trick)
// ============================================================

applyLoadout()
{
    self endon("disconnect");
    self endon("death");

    self cacCleanup();

    self cacSanitize();
    setDvar("dcac_on_" + self.guid, "1");
    logPrint("DCAC;apply;" + self.guid + "\n");
    self useCacLoadout();

    self iPrintLnBold("^2Loadout applied!");
}

useCacLoadout()
{
    self cacSanitize();
    self.pers["class"] = "gamemode";
    self.pers["lastClass"] = "";
    self.class = "gamemode";
    self.lastClass = "";
    self maps\mp\gametypes\_class::giveLoadout(self.team, "gamemode");
}

// A map change clears self.pers and MW3 auto-picks class0 on join, so put an applied loadout back on spawn
watchSpawnLoadout()
{
    self endon("disconnect");
    for (;;)
    {
        self waittill("spawned_player");
        // TEMP: why the loadout is lost after a map change
        logPrint("DCAC;spawn;" + self.guid + ";class=" + self.class + ";flag=" + getDvar("dcac_on_" + self.guid) + ";saved=" + getDvar("dcac_" + self.guid) + "\n");
        if (getDvar("dcac_on_" + self.guid) == "1" && self.class != "gamemode" && !cacModeOwnsLoadout())
            self useCacLoadout();
    }
}

// ============================================================
// GENERIC HUD MENU SYSTEM (MW3 style - monochrome palette)
// ============================================================

// Retail MW3 strike packages (valid lists in _class.gsc also hold cut streaks, left out here).
// Specialist uses the perks as "<perk>_ks"; their cost is the slot (2/4/6) via getStreakCost.
buildStreakData()
{
    level.cac["ks_assault"] = strTok("uav,airdrop_assault,ims,predator_missile,airdrop_sentry_minigun,precision_airstrike,helicopter,littlebird_flock,littlebird_support,remote_mortar,airdrop_remote_tank,ac130,helicopter_flares,airdrop_juggernaut,osprey_gunner", ",");
    level.cac["ks_assault_name"] = strTok("UAV,Care Package,I.M.S.,Predator Missile,Sentry Gun,Precision Airstrike,Attack Helicopter,Strafe Run,AH-6 Overwatch,Reaper,Assault Drone,AC-130,Pave Low,Juggernaut,Osprey Gunner", ",");
    level.cac["ks_support"] = strTok("uav_support,counter_uav,deployable_vest,airdrop_trap,sam_turret,remote_uav,triple_uav,remote_mg_turret,stealth_airstrike,airdrop_juggernaut_recon,escort_airdrop,emp", ",");
    level.cac["ks_support_name"] = strTok("UAV,Counter-UAV,Ballistic Vests,Airdrop Trap,SAM Turret,Recon Drone,Advanced UAV,Remote Sentry,Stealth Bomber,Juggernaut Recon,Escort Airdrop,EMP", ",");

    level.cac["ks_specialist"] = [];
    level.cac["ks_specialist_name"] = [];
    lists = strTok("perk1,perk2,perk3", ",");
    for (l = 0; l < lists.size; l++)
        for (i = 0; i < level.cac[lists[l]].size; i++)
        {
            perk = level.cac[lists[l]][i];
            if (perk == "specialty_twoprimaries")
                continue;
            level.cac["ks_specialist"][level.cac["ks_specialist"].size] = perk + "_ks";
            level.cac["ks_specialist_name"][level.cac["ks_specialist_name"].size] = level.cac[lists[l] + "_name"][i];
        }

    level.cac["streaktypes"] = strTok("streaktype_assault,streaktype_support,streaktype_specialist", ",");
    level.cac["streaktypes_name"] = strTok("Assault,Support,Specialist", ",");
}

// Code name -> display name for every list that has a matching "_name" list
buildNameLookup()
{
    level.cac_names = [];
    extra = strTok("silencer02,silencer03,gp25,m320,hamrhybrid,fmj,zoomscope,reflexsmg,eotechsmg,acogsmg,thermalsmg,reflexlmg,eotechlmg", ",");
    extraName = strTok("Silencer,Silencer,Grenade Launcher,Grenade Launcher,Hybrid Sight,FMJ,Variable Zoom,Red Dot Sight,Holographic Sight,ACOG Scope,Thermal Scope,Red Dot Sight,Holographic Sight", ",");
    for (i = 0; i < extra.size; i++)
        level.cac_names[extra[i]] = extraName[i];
    keys = getArrayKeys(level.cac);
    for (k = 0; k < keys.size; k++)
    {
        if (!isDefined(level.cac[keys[k] + "_name"]))
            continue;
        for (i = 0; i < level.cac[keys[k]].size; i++)
            level.cac_names[level.cac[keys[k]][i]] = level.cac[keys[k] + "_name"][i];
    }
}

cacName(code)
{
    if (!isDefined(code) || code == "none" || code == "specialty_null")
        return "None";
    if (isDefined(level.cac_names[code]))
        return level.cac_names[code];
    return code;
}

// MW3-style layout: dark left column with title and rows, loadout panel on the right.
// Built once per open; every screen after that only swaps text, so there is no redraw.
// Bots hold still while anyone has the menu open (Bot Warfare reads bots_play_* live)
botsPause()
{
    if (!isDefined(level.dcac_menus)) level.dcac_menus = 0;
    level.dcac_menus++;
    if (level.dcac_menus > 1)
        return;
    level.dcac_botplay = [];
    dvars = strTok("bots_play_move,bots_play_fire,bots_play_knife,bots_play_nade,bots_play_killstreak", ",");
    for (i = 0; i < dvars.size; i++)
    {
        level.dcac_botplay[dvars[i]] = getDvar(dvars[i]);
        setDvar(dvars[i], "0");
    }
}

botsResume()
{
    if (!isDefined(level.dcac_menus) || level.dcac_menus <= 0)
        return;
    level.dcac_menus--;
    if (level.dcac_menus > 0)
        return;
    keys = getArrayKeys(level.dcac_botplay);
    for (i = 0; i < keys.size; i++)
        setDvar(keys[i], level.dcac_botplay[keys[i]]);
}

cacBuildUi()
{
    self botsPause();
    self freezeControlsWrapper(true);
    self setClientDvar("actionSlotsHide", "1");

    ui = [];
    all = [];

    // MW3 caps HUD elements per player; past ~27 new ones silently fail (24 here)
    // One dark backdrop, no divider (same look as the BO2 menu)
    all[all.size] = self createBgLocal(0, 0, 640, 480, (0, 0, 0), 0.55, 1);

    ui["title"] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 16, 24, 1.3, "hudbig", (1, 1, 1), 1, 4);
    all[all.size] = ui["title"];

    // MW3 green selection bar
    // vertical position follows the rows (safe area), width follows the left column (full screen)
    ui["hl"] = self createShaderLocal("white", "TOPLEFT", "TOPLEFT", 0, 0, 290, 22, (0.36, 0.6, 0.18), 0.8, 2);
    ui["hl"].horzAlign = "fullscreen";
    ui["hl"].x = 0;
    all[all.size] = ui["hl"];

    ui["rows"] = [];
    for (i = 0; i < 10; i++)
    {
        ui["rows"][i] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 20, cacRowY(i), 1.0, "objective", (0.8, 0.8, 0.8), 0, 4);
        all[all.size] = ui["rows"][i];
    }

    // Loadout panel on the right, controls right under it. Section names ride on the first value of
    // each section (one element per line), so the distinct strings stay close to the item names.
    // Controls line; on pages with descriptions it also explains the highlighted row
    ui["hint"] = self createTextLocal(cacControls(), "TOPLEFT", "TOPRIGHT", -276, 350, 0.8, "objective", (0.75, 0.75, 0.75), 1, 4);
    all[all.size] = ui["hint"];
    valueY = strTok("80,98,116,146,176,194,212,242,272,302", ",");
    ui["vals"] = [];
    for (i = 0; i < valueY.size; i++)
    {
        ui["vals"][i] = self createTextLocal("", "TOPLEFT", "TOPRIGHT", -276, int(valueY[i]), 0.9, "objective", (1, 1, 1), 1, 4);
        all[all.size] = ui["vals"][i];
    }

    self.cac_ui = ui;
    self.cac_huds = all;
}

cacControls()
{
    return "[{+actionslot 1}]/[{+actionslot 2}] Scroll   [{+gostand}] Select   [{+stance}] Back";
}

// Description of the highlighted row above the controls (fixed strings, so few distinct HUD strings)
cacShowHint(descs, index)
{
    if (isDefined(descs) && isDefined(descs[index]))
        self.cac_ui["hint"] setText("^7" + descs[index] + "\n" + cacControls());
    else
        self.cac_ui["hint"] setText(cacControls());
}

cacRowY(i)
{
    return 78 + (i * 24);
}

cacSetVal(i, text, dim)
{
    self.cac_ui["vals"][i] setText(text);
    if (dim) self.cac_ui["vals"][i].color = (0.6, 0.6, 0.6);
    else self.cac_ui["vals"][i].color = (1, 1, 1);
}

cacUpdatePanel()
{
    l = self.pers["gamemodeLoadout"];
    self cacSetVal(0, "^2PRIMARY   ^7" + cacName(l["loadoutPrimary"]), false);
    self cacSetVal(1, cacAttachLine(l["loadoutPrimaryAttachment"], l["loadoutPrimaryAttachment2"]), true);
    self cacSetVal(2, cacName(l["loadoutPrimaryBuff"]), true);
    sec = cacName(l["loadoutSecondary"]);
    if (l["loadoutSecondaryAttachment"] != "none")
        sec = sec + " + " + cacAttachLine(l["loadoutSecondaryAttachment"], l["loadoutSecondaryAttachment2"]);
    self cacSetVal(3, "^2SECONDARY   ^7" + sec, false);
    self cacSetVal(4, "^2PERKS   ^7" + cacName(l["loadoutPerk1"]), false);
    self cacSetVal(5, cacName(l["loadoutPerk2"]), false);
    self cacSetVal(6, cacName(l["loadoutPerk3"]), false);
    self cacSetVal(7, "^2EQUIPMENT   ^7" + cacName(l["loadoutEquipment"]) + " / " + cacName(l["loadoutOffhand"]), false);
    self cacSetVal(8, "^2DEATHSTREAK   ^7" + cacName(l["loadoutDeathstreak"]), false);
    self.cac_ui["vals"][9].fontScale = 0.75;
    self cacSetVal(9, "^2" + streakTypeLabel(l["loadoutStreakType"]) + "   ^7" + cacName(l["loadoutKillstreak1"]) + ", " + cacName(l["loadoutKillstreak2"]) + ", " + cacName(l["loadoutKillstreak3"]), false);
}

streakTypeLabel(t)
{
    if (t == "streaktype_support") return "SUPPORT";
    if (t == "streaktype_specialist") return "SPECIALIST";
    return "ASSAULT";
}

cacAttachLine(a1, a2)
{
    if (isDefined(a2) && a2 != "none")
        return cacName(a1) + " + " + cacName(a2);
    return cacName(a1);
}

showMenu(title, items, hint)
{
    self endon("disconnect");
    self endon("death");

    if (!isDefined(self.cac_ui))
        self cacBuildUi();
    ui = self.cac_ui;

    menuSize = items.size;
    if (menuSize > 10) menuSize = 10;

    ui["title"] setText(title);
    for (i = 0; i < 10; i++)
    {
        if (i < menuSize)
        {
            ui["rows"][i] setText(items[i]);
            ui["rows"][i].color = (0.8, 0.8, 0.8);
            ui["rows"][i].alpha = 1;
        }
        else
            ui["rows"][i].alpha = 0;
    }
    self cacUpdatePanel();

    // a page redrawn after a toggle keeps the cursor on the row the player was on
    index = 0;
    if (isDefined(self.cac_startIndex))
    {
        if (self.cac_startIndex < menuSize) index = self.cac_startIndex;
        self.cac_startIndex = undefined;
    }
    ui["hl"].y = cacRowY(index) - 4;
    if (menuSize > 0) ui["rows"][index].color = (1, 1, 1);
    descs = self.cac_descs;
    self.cac_descs = undefined;
    self cacShowHint(descs, index);

    for (;;)
    {
        command = self waittill_any_return("cac_up", "cac_down", "cac_select", "cac_back");

        if (command == "cac_up" || command == "cac_down")
        {
            ui["rows"][index].color = (0.8, 0.8, 0.8);
            if (command == "cac_up") index--;
            else index++;
            if (index < 0) index = menuSize - 1;
            if (index >= menuSize) index = 0;
            ui["hl"].y = cacRowY(index) - 4;
            ui["rows"][index].color = (1, 1, 1);
            self cacShowHint(descs, index);
            self playLocalSound("mouse_over");
        }
        else if (command == "cac_select")
        {
            self playLocalSound("mouse_click");
            return index;
        }
        else
        {
            self playLocalSound("mouse_click");
            return -1;
        }
    }
}

// ============================================================
// HUD HELPER FUNCTIONS
// ============================================================

createTextLocal(text, align, relative, x, y, fontscale, font, color, alpha, sort)
{
    elem = self createFontString(font, fontscale);
    elem.hidewheninmenu = true;
    elem.foreground = true;
    elem.color = color;
    elem.alpha = alpha;
    elem.sort = sort;
    elem setPoint(align, relative, x, y);
    elem setText(text);
    return elem;
}

// Full-screen 640x480 space, so columns reach the screen edges at any resolution
createBgLocal(x, y, width, height, color, alpha, sort)
{
    elem = self createShaderLocal("white", "TOPLEFT", "TOPLEFT", 0, 0, width, height, color, alpha, sort);
    elem.horzAlign = "fullscreen";
    elem.vertAlign = "fullscreen";
    elem.x = x;
    elem.y = y;
    return elem;
}

createShaderLocal(shader, align, relative, x, y, width, height, color, alpha, sort)
{
    elem = self createIcon(shader, width, height);
    elem.hidewheninmenu = true;
    elem.foreground = true;
    elem.color = color;
    elem.alpha = alpha;
    elem.sort = sort;
    elem setPoint(align, relative, x, y);
    return elem;
}
