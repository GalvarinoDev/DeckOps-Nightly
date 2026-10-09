/*
    DeckOps Settings (T6 / BO2 MP), port of the MW3 offline hub (port_iw5/deckops_cac.gsc)
    Server-side GSC for the local Plutonium LAN server.
    Drop into: storage/t6/raw/scripts/mp/deckops_cac.gsc (MP only; Zombies never loads scripts/mp)

    Hub: Class Editor (Pick 10), Choose Class (BO2's own list), Map / Mode, Bot Warfare.
    - Open: DECKOPS SETTINGS in the pause menu. BO2's pause menu is client Lua, so the button comes from an
      offline-only class.lua override (port_t6/lua, built into mods/deckops_offline/mod.ff; an iwd can't
      override Plutonium's zone copy) that sends menuresponse("class", "deckops_settings").
    - Loadouts go through level.givecustomloadout, which _class::giveloadout calls last (same hook as
      Gun Game / OIC), so no stats are written.
    - Items come from the game's mp/statstable.csv and mp/attachmenttable.csv.

    Controls: Dpad Up/Down scroll, Jump or Use select, B (stance) or ADS back.

    Credits:
        - Divity (k) - Original in-game CAC concept
        - CMT Frosty - HUD string overflow fix pattern
        - DeckOps Community
*/

#include common_scripts\utility;
#include maps\mp\_utility;
#include maps\mp\gametypes\_hud_util;

init()
{
    if (sessionmodeiszombiesgame())
        return;

    precacheshader("white");

    // Every new setText string takes a configstring; clearing everything after this anchor frees them
    level.dcac_anchor = createserverfontstring("default", 1.5);
    level.dcac_anchor settext("anchor");
    level.dcac_anchor.alpha = 0;
    level.dcac_strings = [];
    level.dcac_strcount = 0;

    buildItemData();
    buildNames();

    if (!cacModeOwnsLoadout())
    {
        level.dcac_prevloadout = level.givecustomloadout;
        level.givecustomloadout = ::dcacGiveLoadout;
    }

    level thread onPlayerConnect();
    level thread applyMatchOptions();
}

onPlayerConnect()
{
    for (;;)
    {
        level waittill("connected", player);
        if (player isBotPlayer())
            continue;
        player initCac();
        player thread watchMenuResponse();
        player thread watchInput();
        player thread watchDeath();
    }
}

isBotPlayer()
{
    return (isdefined(self.pers["isBot"]) && self.pers["isBot"]) || self istestclient();
}

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
    if (isdefined(self.cac_ui))
    {
        botsResume();
        self setclientuivisibilityflag("hud_visible", 1);
    }
    if (isdefined(self.cac_huds))
        foreach (e in self.cac_huds)
            if (isdefined(e))
                e destroy();
    self.cac_huds = undefined;
    self.cac_ui = undefined;
    if (isdefined(self.cac_speed))
        self cacLock(false);
    self.cac_open = false;
}

// ---
// Item data from the game's tables

buildItemData()
{
    t = "mp/statstable.csv";
    level.cac = [];
    level.cac_atts = [];
    level.cac_slot = [];
    level.cac_cost = [];

    level.cac["cats_p"] = strtok("weapon_smg,weapon_assault,weapon_cqb,weapon_lmg,weapon_sniper,weapon_special", ",");
    level.cac["cats_p_name"] = strtok("Submachine Guns,Assault Rifles,Shotguns,Light Machine Guns,Sniper Rifles,Specials", ",");
    level.cac["cats_s"] = strtok("weapon_pistol,weapon_launcher,weapon_special", ",");
    level.cac["cats_s_name"] = strtok("Pistols,Launchers,Specials", ",");
    lists = strtok("perk1,perk2,perk3,lethal,tactical,wildcard,streak", ",");
    foreach (k in lists)
        level.cac[k] = [];

    for (i = 0; i < 256; i++)
    {
        row = tablelookuprownum(t, 0, i);
        if (row < 0)
            continue;
        group = tablelookupcolumnforrow(t, row, 2);
        ref = tablelookupcolumnforrow(t, row, 4);
        inCac = tablelookupcolumnforrow(t, row, 12);
        slot = tablelookupcolumnforrow(t, row, 13);
        if (ref == "")
            continue;

        if (group == "killstreak")
        {
            if (inCac == "0" && ref != "killstreak_null")
            {
                level.cac_cost[ref] = int(tablelookupcolumnforrow(t, row, 16));
                level.cac["streak"] = insertByCost(level.cac["streak"], ref);
            }
            continue;
        }
        if (inCac != "1")
            continue;
        // DLC items (Peacekeeper) may be missing from the install
        if (tablelookupcolumnforrow(t, row, 15) != "")
            continue;

        if (group == "specialty")
        {
            if (slot == "specialty1") addTo("perk1", ref);
            else if (slot == "specialty2") addTo("perk2", ref);
            else if (slot == "specialty3") addTo("perk3", ref);
        }
        else if (group == "bonuscard")
            addTo("wildcard", ref);
        else if (group == "weapon_grenade")
        {
            if (slot == "primarygrenade") addTo("lethal", ref);
            else if (slot == "specialgrenade") addTo("tactical", ref);
        }
        else if (issubstr(group, "weapon_") && (slot == "primary" || slot == "secondary"))
        {
            addTo("w_" + group + "_" + slot, ref);
            level.cac_slot[ref] = slot;
            // Table codes are per class (reflex_pistol, silencer_shotgun, rf_fast); the weapon name uses the base code
            atts = [];
            foreach (a in strtok(tablelookupcolumnforrow(t, row, 8), " "))
            {
                base = strtok(a, "_")[0];
                if (!isinarray(atts, base))
                    atts[atts.size] = base;
            }
            level.cac_atts[ref] = atts;
        }
    }
}

addTo(key, ref)
{
    if (!isdefined(level.cac[key]))
        level.cac[key] = [];
    level.cac[key][level.cac[key].size] = ref;
}

insertByCost(list, ref)
{
    out = [];
    placed = false;
    foreach (k in list)
    {
        if (!placed && level.cac_cost[ref] < level.cac_cost[k])
        {
            out[out.size] = ref;
            placed = true;
        }
        out[out.size] = k;
    }
    if (!placed)
        out[out.size] = ref;
    return out;
}

// Pair rules from mp/attachmenttable.csv (column 11 lists what each attachment can go with)
attCompatible(a, b)
{
    if (a == b)
        return false;
    return isinarray(strtok(tablelookup("mp/attachmenttable.csv", 4, a, 11), " "), b);
}

attIndex(a)
{
    return int(tablelookup("mp/attachmenttable.csv", 4, a, 0));
}

// ---
// Display names (keyed by code; perks by their first specialty)

buildNames()
{
    level.cac_names = [];
    addNames("mp7,evoskorpion,pdw57,qcw05,insas,vector,peacekeeper,xm8,scar,an94,sig556,type95,sa58,saritch,hk416,tar21,mk48,qbb95,lsat,hamr,ballista,svu,dsr50,as50,870mcs,srm1216,saiga12,ksg,riotshield,kard,fnp45,beretta93r,judge,fiveseven,smaw,fhj18,usrpg,crossbow,knife_ballistic",
        "MP7,Skorpion EVO,PDW-57,Chicom CQB,MSMC,Vector K10,Peacekeeper,M8A1,SCAR-H,AN-94,SWAT-556,Type 25,FAL OSW,SMR,M27,MTAR,Mk 48,QBB LSW,LSAT,HAMR,Ballista,SVU-AS,DSR 50,XPR-50,R870 MCS,M1216,S12,KSG,Assault Shield,KAP-40,Tac-45,B23R,Executioner,Five-seven,SMAW,FHJ-18 AA,RPG,Crossbow,Ballistic Knife");
    addNames("acog,dualclip,dualoptic,dw,extbarrel,extclip,fastads,fmj,gl,grip,holo,ir,is,mms,rangefinder,reflex,rf,sf,silencer,stackfire,stalker,steadyaim,swayreduc,tacknife,vzoom",
        "ACOG Sight,Fast Mag,Hybrid Optic,Dual Wield,Long Barrel,Extended Clip,Quickdraw,FMJ,Launcher,Foregrip,EOTech,Dual Band,Iron Sights,MMS,Target Finder,Reflex,Rapid Fire,Select Fire,Suppressor,Tri-Bolt,Stock,Laser Sight,Ballistics CPU,Tactical Knife,Variable Zoom");
    addNames("specialty_movefaster,specialty_flakjacket,specialty_nottargetedbyairsupport,specialty_earnmoremomentum,specialty_gpsjammer,specialty_immunecounteruav,specialty_scavenger,specialty_immunenvthermal,specialty_fastweaponswitch,specialty_bulletflinch,specialty_fastmantle,specialty_showenemyequipment,specialty_quieter,specialty_longersprint,specialty_stunprotection,specialty_loudenemies",
        "Lightweight,Flak Jacket,Blind Eye,Hardline,Ghost,Hard Wired,Scavenger,Cold Blooded,Fast Hands,Toughness,Dexterity,Engineer,Dead Silence,Extreme Conditioning,Tactical Mask,Awareness");
    addNames("frag_grenade,hatchet,sticky_grenade,satchel_charge,bouncingbetty,claymore,willy_pete,concussion_grenade,emp_grenade,sensor_grenade,flash_grenade,proximity_grenade,pda_hack,tactical_insertion,trophy_system",
        "Frag,Combat Axe,Semtex,C4,Bouncing Betty,Claymore,Smoke Grenade,Concussion,EMP Grenade,Sensor Grenade,Flashbang,Shock Charge,Black Hat,Tactical Insertion,Trophy System");
    addNames("bonuscard_primary_gunfighter,bonuscard_secondary_gunfighter,bonuscard_overkill,bonuscard_perk_1_greed,bonuscard_perk_2_greed,bonuscard_perk_3_greed,bonuscard_danger_close,bonuscard_two_tacticals",
        "Primary Gunfighter,Secondary Gunfighter,Overkill,Perk 1 Greed,Perk 2 Greed,Perk 3 Greed,Danger Close,Tactician");
    addNames("killstreak_rcbomb,killstreak_spyplane,killstreak_missile_drone,killstreak_counteruav,killstreak_supply_drop,killstreak_microwave_turret,killstreak_remote_missile,killstreak_planemortar,killstreak_auto_turret,killstreak_minigun,killstreak_m32,killstreak_qrdrone,killstreak_ai_tank_drop,killstreak_helicopter_comlink,killstreak_spyplane_direction,killstreak_helicopter_guard,killstreak_straferun,killstreak_emp,killstreak_remote_mortar,killstreak_helicopter_player_gunner,killstreak_dogs,killstreak_missile_swarm",
        "RC-XD,UAV,Hunter Killer,Counter-UAV,Care Package,Guardian,Hellstorm Missile,Lightning Strike,Sentry Gun,Death Machine,War Machine,Dragonfire,A.G.R.,Stealth Chopper,Orbital VSAT,Escort Drone,Warthog,EMP Systems,Lodestar,VTOL Warship,K9 Unit,Swarm");
}

addNames(codes, names)
{
    c = strtok(codes, ",");
    n = strtok(names, ",");
    for (i = 0; i < c.size; i++)
        level.cac_names[c[i]] = n[i];
}

cacName(code)
{
    if (!isdefined(code) || code == "none")
        return "None";
    if (issubstr(code, "|"))
        code = strtok(code, "|")[0];
    if (isdefined(level.cac_names[code]))
        return level.cac_names[code];
    return code;
}

// ---
// Loadout storage: self.pers["dcac"], saved per player in server dvars dcac_<guid> (picks) and
// dcac_on_<guid> (use it), so it survives map changes, and in scriptdata/deckops_class_<guid>.txt
// (same two values, one per line), so it survives a server restart

cacKeys()
{
    return strtok("p,p_a1,p_a2,p_a3,s,s_a1,s_a2,lethal,lethal_n,tac,tac_n,perk1,perk1b,perk2,perk2b,perk3,perk3b,wc1,wc2,wc3,ks1,ks2,ks3", ",");
}

initCac()
{
    keys = cacKeys();
    l = [];
    foreach (k in keys)
        l[k] = "none";
    l["p"] = "tar21"; l["p_a1"] = "reflex"; l["s"] = "fiveseven";
    l["lethal"] = "frag_grenade"; l["lethal_n"] = "1"; l["tac"] = "concussion_grenade"; l["tac_n"] = "1";
    l["perk1"] = "specialty_movefaster|specialty_fallheight"; l["perk2"] = "specialty_bulletflinch";
    l["perk3"] = "specialty_fastmantle|specialty_fastladderclimb|specialty_sprintrecovery|specialty_fastmeleerecovery";
    l["ks1"] = "killstreak_rcbomb"; l["ks2"] = "killstreak_spyplane"; l["ks3"] = "killstreak_missile_drone";

    self cacReadFile();
    saved = getdvar("dcac_" + self.guid);
    if (saved != "")
    {
        vals = strtok(saved, ",");
        if (vals.size == keys.size)
            for (i = 0; i < keys.size; i++)
                l[keys[i]] = vals[i];
    }
    self.pers["dcac"] = l;
}

cacSave()
{
    str = "";
    foreach (k in cacKeys())
    {
        if (str != "") str += ",";
        str += self.pers["dcac"][k];
    }
    setdvar("dcac_" + self.guid, str);
    self cacWriteFile();
}

cacSetOn(on)
{
    setdvar("dcac_on_" + self.guid, on);
    self cacWriteFile();
}

cacFile()
{
    return "deckops_class_" + self.guid + ".txt";
}

cacWriteFile()
{
    f = fs_fopen(self cacFile(), "write");
    fs_writeline(f, getdvar("dcac_" + self.guid));
    fs_writeline(f, getdvar("dcac_on_" + self.guid));
    fs_fclose(f);
}

// Fresh server (no dvars yet): load the class saved by an earlier session
cacReadFile()
{
    if (getdvar("dcac_" + self.guid) != "" || !fs_testfile(self cacFile()))
        return;
    f = fs_fopen(self cacFile(), "read");
    picks = fs_readline(f);
    on = fs_readline(f);
    fs_fclose(f);
    // the "use it" line may be empty or missing (never applied)
    if (isdefined(picks) && strtok(picks, "\r\n").size == 1)
        setdvar("dcac_" + self.guid, strtok(picks, "\r\n")[0]);
    if (isdefined(on) && strtok(on, "\r\n").size == 1)
        setdvar("dcac_on_" + self.guid, strtok(on, "\r\n")[0]);
}

cacGet(key)
{
    return self.pers["dcac"][key];
}

cacSet(key, value)
{
    self.pers["dcac"][key] = value;
    self cacSave();
}

// Pick 10: refuses a change that would go over the allocation
cacTry(key, value)
{
    old = self.pers["dcac"][key];
    self.pers["dcac"][key] = value;
    if (self cacPoints() > cacMaxPoints())
    {
        self.pers["dcac"][key] = old;
        self iprintlnbold("^1Not enough points (" + self cacPoints() + "/" + cacMaxPoints() + ")");
        return false;
    }
    self cacSave();
    return true;
}

cacMaxPoints()
{
    if (isdefined(level.maxallocation) && level.maxallocation > 0)
        return level.maxallocation;
    return 10;
}

cacPoints()
{
    l = self.pers["dcac"];
    p = 0;
    foreach (k in strtok("p,p_a1,p_a2,p_a3,s,s_a1,s_a2,perk1,perk1b,perk2,perk2b,perk3,perk3b,wc1,wc2,wc3", ","))
        if (l[k] != "none")
            p++;
    if (l["lethal"] != "none") p += int(l["lethal_n"]);
    if (l["tac"] != "none") p += int(l["tac_n"]);
    return p;
}

hasWc(ref)
{
    return self cacGet("wc1") == ref || self cacGet("wc2") == ref || self cacGet("wc3") == ref;
}

attKeys(slot)
{
    if (slot == "p")
        return strtok("p_a1,p_a2,p_a3", ",");
    return strtok("s_a1,s_a2", ",");
}

maxAtts(slot)
{
    if (slot == "p")
    {
        if (self hasWc("bonuscard_primary_gunfighter")) return 3;
        return 2;
    }
    if (self hasWc("bonuscard_secondary_gunfighter")) return 2;
    return 1;
}

// Tactical Insertion, Trophy System and Black Hat come one at a time
tacMulti(t)
{
    return t != "tactical_insertion" && t != "trophy_system" && t != "pda_hack";
}

// Brings everything back inside the wildcard rules after a wildcard or weapon change
cacSanitize()
{
    foreach (slot in strtok("p,s", ","))
    {
        w = self cacGet(slot);
        if (w != "none" && !isdefined(level.cac_slot[w]))
        {
            self cacSet(slot, "none");
            w = "none";
        }
        if (slot == "s" && w != "none" && level.cac_slot[w] == "primary" && !self hasWc("bonuscard_overkill"))
        {
            self cacSet("s", "none");
            w = "none";
        }
        // Each attachment stays in its own row; the wildcard row needs Gunfighter
        kept = [];
        keys = attKeys(slot);
        for (i = 0; i < keys.size; i++)
        {
            a = self cacGet(keys[i]);
            ok = a != "none" && w != "none" && isdefined(level.cac_atts[w]) && isinarray(level.cac_atts[w], a) && i < self maxAtts(slot);
            foreach (b in kept)
                if (ok && !attCompatible(b, a))
                    ok = false;
            if (ok)
                kept[kept.size] = a;
            else
                self cacSet(keys[i], "none");
        }
    }
    for (t = 1; t <= 3; t++)
        if (!self hasWc("bonuscard_perk_" + t + "_greed") || self cacGet("perk" + t) == "none")
            self cacSet("perk" + t + "b", "none");
    if (self cacGet("lethal") != "none" && !isinarray(level.cac["lethal"], self cacGet("lethal")) && !self hasWc("bonuscard_two_tacticals"))
        self cacSet("lethal", "none");
    if (!self hasWc("bonuscard_danger_close"))
        self cacSet("lethal_n", "1");
    if (!tacMulti(self cacGet("tac")))
        self cacSet("tac_n", "1");
}

// ---
// Loadout hook: _class::giveloadout calls level.givecustomloadout last and uses its return as the spawn weapon

cacUsesDeckops()
{
    return !self isBotPlayer() && isdefined(self.pers["dcac"]) && getdvar("dcac_on_" + self.guid) == "1";
}

dcacGiveLoadout()
{
    if (!self cacUsesDeckops())
    {
        if (isdefined(level.dcac_prevloadout))
            return self [[level.dcac_prevloadout]]();
        return undefined;
    }

    self takeallweapons();

    // perks first: Scavenger and friends are checked while giving weapons
    self.specialty = [];
    foreach (k in strtok("perk1,perk1b,perk2,perk2b,perk3,perk3b", ","))
        if (self cacGet(k) != "none")
            foreach (s in strtok(self cacGet(k), "|"))
                self.specialty[self.specialty.size] = s;
    self maps\mp\gametypes\_class::register_perks();
    self maps\mp\gametypes\_class::cac_selector();

    self giveweapon("knife_mp");
    prim = self cacWeaponName("p");
    sec = self cacWeaponName("s");
    spawnweapon = "";
    if (sec != "")
    {
        self giveweapon(sec);
        if (self hasperk("specialty_extraammo")) self givemaxammo(sec);
        spawnweapon = sec;
    }
    if (prim != "")
    {
        self giveweapon(prim);
        if (self hasperk("specialty_extraammo")) self givemaxammo(prim);
        spawnweapon = prim;
        self.pers["primaryWeapon"] = self cacGet("p");
    }
    if (prim == "" || sec == "")
    {
        self giveweapon("knife_held_mp");
        if (spawnweapon == "") spawnweapon = "knife_held_mp";
    }
    self setspawnweapon(spawnweapon);
    self.spawnweapon = spawnweapon;
    self.pers["spawnWeapon"] = spawnweapon;

    self.grenadetypeprimary = undefined;
    self.grenadetypesecondary = undefined;
    if (self cacGet("lethal") != "none")
    {
        g = self cacGet("lethal") + "_mp";
        n = int(self cacGet("lethal_n"));
        self giveweapon(g);
        self setweaponammoclip(g, n);
        self switchtooffhand(g);
        self.grenadetypeprimary = g;
        self.grenadetypeprimarycount = n;
        if (n > 1) self dualgrenadesactive();
    }
    if (self cacGet("tac") != "none")
    {
        g = self cacGet("tac") + "_mp";
        n = int(self cacGet("tac_n"));
        self setoffhandsecondaryclass(g);
        self giveweapon(g);
        self setweaponammoclip(g, n);
        self.grenadetypesecondary = g;
        self.grenadetypesecondarycount = n;
    }

    self cacGiveStreaks();
    if (prim != "")
        self maps\mp\teams\_teams::set_player_model(self.team, prim);
    return spawnweapon;
}

// Weapon name the game builds: base[_dw]_mp+att+att, attachments in attachment table order
cacWeaponName(slot)
{
    w = self cacGet(slot);
    if (w == "none")
        return "";
    atts = [];
    dw = false;
    foreach (k in attKeys(slot))
    {
        a = self cacGet(k);
        if (a == "dw") dw = true;
        else if (a != "none") atts[atts.size] = a;
    }
    for (i = 0; i < atts.size; i++)
        for (j = i + 1; j < atts.size; j++)
            if (attIndex(atts[j]) < attIndex(atts[i]))
            {
                tmp = atts[i]; atts[i] = atts[j]; atts[j] = tmp;
            }
    name = w;
    if (dw) name += "_dw";
    name += "_mp";
    foreach (a in atts)
        name += "+" + a;
    return name;
}

// Same as _class::givekillstreaks, from the DeckOps picks instead of the stats class.
// Earning reads self.killstreak (_globallogic_score::_setplayermomentum).
cacGiveStreaks()
{
    self.killstreak = [];
    if (!level.loadoutkillstreaksenabled)
        return;
    sorted = [];
    for (n = 1; n <= 3; n++)
    {
        ks = self cacGet("ks" + n);
        if (ks == "none")
            continue;
        self.killstreak[self.killstreak.size] = ks;
        if (!(isdefined(level.usingmomentum) && level.usingmomentum))
            continue;
        type = maps\mp\killstreaks\_killstreaks::getkillstreakbymenuname(ks);
        if (!isdefined(type))
            continue;
        weapon = maps\mp\killstreaks\_killstreaks::getkillstreakweapon(type);
        self giveweapon(weapon);
        if (isdefined(level.usingscorestreaks) && level.usingscorestreaks)
        {
            if (maps\mp\killstreaks\_killstreak_weapons::isheldkillstreakweapon(weapon))
            {
                if (!isdefined(self.pers["held_killstreak_ammo_count"][weapon])) self.pers["held_killstreak_ammo_count"][weapon] = 0;
                if (!isdefined(self.pers["held_killstreak_clip_count"][weapon])) self.pers["held_killstreak_clip_count"][weapon] = 0;
                if (self.pers["held_killstreak_ammo_count"][weapon] > 0)
                {
                    self setweaponammoclip(weapon, self.pers["held_killstreak_clip_count"][weapon]);
                    self setweaponammostock(weapon, self.pers["held_killstreak_ammo_count"][weapon] - self.pers["held_killstreak_clip_count"][weapon]);
                }
                else
                    self maps\mp\gametypes\_class::setweaponammooverall(weapon, 0);
            }
            else
            {
                quantity = self.pers["killstreak_quantity"][weapon];
                if (!isdefined(quantity)) quantity = 0;
                self setweaponammoclip(weapon, quantity);
            }
        }
        d = spawnstruct();
        d.cost = level.killstreaks[type].momentumcost;
        d.weapon = weapon;
        i = 0;
        while (i < sorted.size && sorted[i].cost <= d.cost)
            i++;
        for (j = sorted.size; j > i; j--)
            sorted[j] = sorted[j - 1];
        sorted[i] = d;
    }
    order = strtok("4,2,1", ",");
    for (i = 0; i < order.size; i++)
    {
        if (i < sorted.size) self setactionslot(int(order[i]), "weapon", sorted[i].weapon);
        else self setactionslot(int(order[i]), "");
    }
}

// Gun Game, One in the Chamber, Sharpshooter and Sticks and Stones hand out their own loadouts
cacModeOwnsLoadout()
{
    switch (level.gametype)
    {
        case "gun":
        case "oic":
        case "shrp":
        case "sas":
            return true;
    }
    return false;
}

// ---
// Opening, input, class list

// Dpad and W/S come through notifyonplayercommand (Plutonium T6); the actionslot*buttonpressed
// polls returned nothing. Jump, use, knife and ADS poll fine; the stick is polled on its own.
// A held button counts once.
watchInput()
{
    self endon("disconnect");
    self notifyonplayercommand("cac_up", "+actionslot 1");
    self notifyonplayercommand("cac_up", "+forward");
    self notifyonplayercommand("cac_down", "+actionslot 2");
    self notifyonplayercommand("cac_down", "+back");
    held = [];
    foreach (c in strtok("cac_up,cac_down,cac_select,cac_back", ","))
        held[c] = true;
    for (;;)
    {
        wait 0.05;
        if (!self.cac_open)
        {
            // anything held while opening (the combo itself) must be let go first
            foreach (c in getarraykeys(held))
                held[c] = true;
            continue;
        }
        now = [];
        now["cac_select"] = self jumpbuttonpressed() || self usebuttonpressed();
        now["cac_back"] = self stancebuttonpressed() || self adsbuttonpressed();
        now["cac_up"] = false;
        now["cac_down"] = false;
        move = self getnormalizedmovement();
        if (isdefined(move))
        {
            now["cac_up"] = move[0] > 0.6;
            now["cac_down"] = move[0] < -0.6;
        }
        foreach (c in getarraykeys(now))
        {
            if (now[c] && !held[c])
                self notify(c);
            held[c] = now[c];
        }
    }
}

watchMenuResponse()
{
    self endon("disconnect");
    for (;;)
    {
        self waittill("menuresponse", menu, response);
        // TEMP: BO2 menu names, to confirm what reaches the server
        logprint("DCAC;menu;" + self.guid + ";" + menu + ";" + response + "\n");
        // DECKOPS SETTINGS in the pause menu (offline-only class.lua override in the game's Plutonium folder)
        if (menu == "class" && response == "deckops_settings" && !self.cac_open && self.sessionstate == "playing")
        {
            self.cac_open = true;
            self thread openHubMenu();
        }
        // A class picked from BO2's list replaces the DeckOps loadout. The pick before the first
        // spawn of a map doesn't count, so an applied loadout survives map changes.
        if (menu == "changeclass" && response != "back" && ((isdefined(self.cac_choosing) && self.cac_choosing) || self.sessionstate == "playing"))
            self cacSetOn("0");
        if (menu == "changeclass")
            self.cac_choosing = false;
    }
}

openStockClassList()
{
    self cacCleanup();
    self.cac_choosing = true;
    self openmenu("changeclass");
}

// With nothing saved yet, start the editor from the class in use (reads only)
cacSeedFromCurrent()
{
    if (getdvar("dcac_" + self.guid) != "" || !isdefined(self.class_num) || cacModeOwnsLoadout())
        return;
    n = self.class_num;
    foreach (k in cacKeys())
        self.pers["dcac"][k] = "none";
    self cacParseWeapon("p", self getloadoutweapon(n, "primary"));
    self cacParseWeapon("s", self getloadoutweapon(n, "secondary"));

    perks = self getloadoutperks(n);
    for (t = 1; t <= 3; t++)
        foreach (ref in level.cac["perk" + t])
            if (isinarray(perks, strtok(ref, "|")[0]))
            {
                if (self.pers["dcac"]["perk" + t] == "none") self.pers["dcac"]["perk" + t] = ref;
                else self.pers["dcac"]["perk" + t + "b"] = ref;
            }

    g = self getloadoutitemref(n, "primarygrenade");
    if (isinarray(level.cac["lethal"], g) || isinarray(level.cac["tactical"], g))
    {
        self.pers["dcac"]["lethal"] = g;
        self.pers["dcac"]["lethal_n"] = "" + max(1, self getloadoutitem(n, "primarygrenadecount"));
    }
    g = self getloadoutitemref(n, "specialgrenade");
    if (isinarray(level.cac["tactical"], g))
    {
        self.pers["dcac"]["tac"] = g;
        self.pers["dcac"]["tac_n"] = "" + max(1, self getloadoutitem(n, "specialgrenadecount"));
    }

    if (isdefined(self.killstreak))
        for (i = 0; i < self.killstreak.size && i < 3; i++)
            self.pers["dcac"]["ks" + (i + 1)] = self.killstreak[i];

    // wildcards follow from what the class holds
    wc = [];
    if (self.pers["dcac"]["p_a3"] != "none") wc[wc.size] = "bonuscard_primary_gunfighter";
    if (self.pers["dcac"]["s_a2"] != "none") wc[wc.size] = "bonuscard_secondary_gunfighter";
    if (self.pers["dcac"]["s"] != "none" && level.cac_slot[self.pers["dcac"]["s"]] == "primary") wc[wc.size] = "bonuscard_overkill";
    for (t = 1; t <= 3; t++)
        if (self.pers["dcac"]["perk" + t + "b"] != "none") wc[wc.size] = "bonuscard_perk_" + t + "_greed";
    if (int(self.pers["dcac"]["lethal_n"]) > 1) wc[wc.size] = "bonuscard_danger_close";
    if (isinarray(level.cac["tactical"], self.pers["dcac"]["lethal"])) wc[wc.size] = "bonuscard_two_tacticals";
    for (i = 0; i < wc.size && i < 3; i++)
        self.pers["dcac"]["wc" + (i + 1)] = wc[i];

    self cacSanitize();
    self cacSave();
}

cacParseWeapon(slot, w)
{
    if (!isdefined(w))
        return;
    toks = strtok(w, "+");
    if (toks.size == 0 || !issubstr(toks[0], "_mp"))
        return;
    base = getsubstr(toks[0], 0, toks[0].size - 3);
    keys = attKeys(slot);
    k = 0;
    if (issubstr(base, "_dw"))
    {
        base = getsubstr(base, 0, base.size - 3);
        self.pers["dcac"][keys[0]] = "dw";
        k = 1;
    }
    if (!isdefined(level.cac_slot[base]))
        return;
    self.pers["dcac"][slot] = base;
    for (i = 1; i < toks.size && k < keys.size; i++)
    {
        self.pers["dcac"][keys[k]] = toks[i];
        k++;
    }
}

// ---
// Hub

openHubMenu()
{
    self endon("disconnect");
    self endon("death");

    self cacSeedFromCurrent();
    for (;;)
    {
        items = strtok("Class Editor,Choose Class,Map / Mode,Bot Warfare", ",");
        d = [];
        d[0] = "Build your class: weapons, perks, wildcards, streaks.";
        d[1] = "Use one of BO2's own classes instead.";
        d[2] = "Change the mode, the map and the match limits.";
        d[3] = "How many bots, how tough, and how they play.";
        self.cac_descs = d;
        r = self showMenu("DECKOPS SETTINGS", items);
        switch (r)
        {
            case 0:
            case 1:
                if (cacModeOwnsLoadout())
                    self iprintlnbold("^1This mode uses its own loadouts");
                else if (r == 1)
                {
                    self openStockClassList();
                    return;
                }
                else if (self openCACMenu())
                    return;
                break;
            case 2:
                if (self openMatchMenu())
                    return;
                break;
            case 3:
                self openBotMenu();
                break;
            default:
                self cacCleanup();
                return;
        }
    }
}

// Paged list: 9 choices + More / Back to Start. Returns the picked index or -1.
pickList(title, names)
{
    page = 0;
    for (;;)
    {
        first = page * 9;
        rows = [];
        for (i = first; i < names.size && i < first + 9; i++)
            rows[rows.size] = names[i];
        more = first + 9 < names.size;
        if (more) rows[rows.size] = "More";
        else if (page > 0) rows[rows.size] = "Back to Start";
        r = self showMenu(title, rows);
        if (r == -1)
            return -1;
        if (r >= 9 || first + r >= names.size)
        {
            if (more) page++;
            else page = 0;
            continue;
        }
        return first + r;
    }
}

namesOf(codes)
{
    out = [];
    foreach (c in codes)
        out[out.size] = cacName(c);
    return out;
}

withNone(codes)
{
    out = [];
    out[0] = "none";
    foreach (c in codes)
        out[out.size] = c;
    return out;
}

// ---
// Class Editor (returns true when the loadout was applied and the menu closed)

openCACMenu()
{
    items = strtok("Primary,Secondary,Lethal,Tactical,Perk 1,Perk 2,Perk 3,Wildcards,Scorestreaks,Apply Loadout", ",");
    d = [];
    d[0] = "Primary weapon and its attachments.";
    d[1] = "Secondary weapon. Overkill: a second primary.";
    d[2] = "Lethal equipment. Danger Close: carry two.";
    d[3] = "Tactical equipment.";
    d[4] = "Perk 1. Perk 1 Greed: pick a second one.";
    d[5] = "Perk 2. Perk 2 Greed: pick a second one.";
    d[6] = "Perk 3. Perk 3 Greed: pick a second one.";
    d[7] = "Up to three wildcards, each costs a point.";
    d[8] = "Three scorestreaks, earned by score.";
    d[9] = "Use this class now and on every spawn.";
    index = 0;
    for (;;)
    {
        self.cac_descs = d;
        self.cac_startIndex = index;
        r = self showMenu("CLASS EDITOR   " + self cacPoints() + "/" + cacMaxPoints(), items);
        if (r == -1)
            return false;
        index = r;
        switch (r)
        {
            case 0: self editWeaponSlot("p"); break;
            case 1: self editWeaponSlot("s"); break;
            case 2: self pickLethal(); break;
            case 3: self pickTactical(); break;
            case 4: case 5: case 6: self pickPerk(r - 3); break;
            case 7: self pickWildcards(); break;
            case 8: self pickStreaks(); break;
            case 9: self applyLoadout(); return true;
        }
    }
}

editWeaponSlot(slot)
{
    title = "PRIMARY";
    if (slot == "s") title = "SECONDARY";
    keys = attKeys(slot);
    index = 0;
    for (;;)
    {
        items = [];
        d = [];
        items[0] = "Weapon: " + cacName(self cacGet(slot));
        d[0] = "Pick the weapon.";
        for (i = 0; i < keys.size; i++)
        {
            label = "Attachment " + (i + 1);
            if (i >= baseAtts(slot))
            {
                label += " (Wildcard)";
                d[i + 1] = "Adds the " + cacName(gunfighterOf(slot)) + " wildcard.";
            }
            else
                d[i + 1] = "Pick or remove this attachment.";
            items[i + 1] = label + ": " + cacName(self cacGet(keys[i]));
        }
        self.cac_descs = d;
        self.cac_startIndex = index;
        r = self showMenu(title, items);
        if (r == -1)
            return;
        index = r;
        if (r == 0)
            self pickWeapon(slot);
        else
            self pickAttachSlot(slot, r - 1);
    }
}

pickWeapon(slot)
{
    type = "secondary";
    cats = level.cac["cats_s"];
    catNames = level.cac["cats_s_name"];
    if (slot == "p" || self hasWc("bonuscard_overkill"))
    {
        type = "primary";
        cats = level.cac["cats_p"];
        catNames = level.cac["cats_p_name"];
    }
    names = [];
    names[0] = "None";
    foreach (c in catNames)
        names[names.size] = c;
    r = self pickList("Category", names);
    if (r == -1)
        return;
    if (r == 0)
    {
        self clearAtts(slot);
        self cacSet(slot, "none");
        return;
    }
    list = level.cac["w_" + cats[r - 1] + "_" + type];
    if (!isdefined(list) || list.size == 0)
        return;
    r = self pickList(catNames[r - 1], namesOf(list));
    if (r == -1)
        return;
    old = self cacGet(slot);
    self clearAtts(slot);
    if (!self cacTry(slot, list[r]))
        self cacSet(slot, old);
}

// A new weapon starts bare, and its Gunfighter goes with the attachments
clearAtts(slot)
{
    foreach (k in attKeys(slot))
        self cacSet(k, "none");
    self removeWc(gunfighterOf(slot));
}

// Attachments without a wildcard; the slot after them needs Gunfighter
baseAtts(slot)
{
    if (slot == "p")
        return 2;
    return 1;
}

gunfighterOf(slot)
{
    if (slot == "p")
        return "bonuscard_primary_gunfighter";
    return "bonuscard_secondary_gunfighter";
}

// One attachment slot; the wildcard slot turns Gunfighter on and off with its attachment
pickAttachSlot(slot, i)
{
    w = self cacGet(slot);
    if (w == "none" || !isdefined(level.cac_atts[w]) || level.cac_atts[w].size == 0)
    {
        self iprintlnbold("^1This weapon takes no attachments");
        return;
    }
    keys = attKeys(slot);
    key = keys[i];
    others = [];
    foreach (k in keys)
        if (k != key && self cacGet(k) != "none")
            others[others.size] = self cacGet(k);

    codes = [];
    names = [];
    if (self cacGet(key) != "none")
    {
        codes[0] = "none";
        names[0] = "Remove";
    }
    foreach (a in level.cac_atts[w])
    {
        ok = !isinarray(others, a);
        foreach (b in others)
            if (ok && !attCompatible(b, a))
                ok = false;
        if (ok)
        {
            codes[codes.size] = a;
            names[names.size] = cacName(a);
        }
    }
    r = self pickList("Attachment " + (i + 1), names);
    if (r == -1)
        return;

    wc = gunfighterOf(slot);
    isWc = i >= baseAtts(slot);
    if (codes[r] == "none")
    {
        self cacSet(key, "none");
        if (isWc)
            self removeWc(wc);
        return;
    }
    if (isWc && !self hasWc(wc))
    {
        if (!self addWc(wc))
            return;
        if (!self cacTry(key, codes[r]))
            self removeWc(wc);
        return;
    }
    self cacTry(key, codes[r]);
}

// Puts a wildcard in a free slot, inside the Pick 10 points
addWc(w)
{
    for (i = 1; i <= 3; i++)
        if (self cacGet("wc" + i) == "none")
            return self cacTry("wc" + i, w);
    self iprintlnbold("^1Three wildcards at most");
    return false;
}

removeWc(w)
{
    for (i = 1; i <= 3; i++)
        if (self cacGet("wc" + i) == w)
            self cacSet("wc" + i, "none");
}

pickCount(title)
{
    return self pickList(title, strtok("1,2", ",")) + 1;
}

pickLethal()
{
    codes = withNone(level.cac["lethal"]);
    // Tactician: a tactical in the lethal slot
    if (self hasWc("bonuscard_two_tacticals"))
        foreach (t in level.cac["tactical"])
            codes[codes.size] = t;
    r = self pickList("Lethal", namesOf(codes));
    if (r == -1)
        return;
    self cacSet("lethal_n", "1");
    if (!self cacTry("lethal", codes[r]) || codes[r] == "none")
        return;
    if (self hasWc("bonuscard_danger_close") && self pickCount("How Many") == 2)
        self cacTry("lethal_n", "2");
}

pickTactical()
{
    codes = withNone(level.cac["tactical"]);
    r = self pickList("Tactical", namesOf(codes));
    if (r == -1)
        return;
    self cacSet("tac_n", "1");
    if (!self cacTry("tac", codes[r]) || codes[r] == "none")
        return;
    if (tacMulti(codes[r]) && self pickCount("How Many") == 2)
        self cacTry("tac_n", "2");
}

pickPerk(tier)
{
    codes = withNone(level.cac["perk" + tier]);
    r = self pickList("Perk " + tier, namesOf(codes));
    if (r == -1)
        return;
    self cacSet("perk" + tier + "b", "none");
    if (!self cacTry("perk" + tier, codes[r]) || codes[r] == "none" || !self hasWc("bonuscard_perk_" + tier + "_greed"))
        return;
    second = [];
    foreach (c in codes)
        if (c != codes[r])
            second[second.size] = c;
    r = self pickList("Perk " + tier + " Greed", namesOf(second));
    if (r != -1)
        self cacTry("perk" + tier + "b", second[r]);
}

pickWildcards()
{
    list = level.cac["wildcard"];
    index = 0;
    for (;;)
    {
        names = [];
        foreach (w in list)
        {
            if (self hasWc(w)) names[names.size] = cacName(w) + "   ^2ON";
            else names[names.size] = cacName(w);
        }
        self.cac_startIndex = index;
        r = self showMenu("WILDCARDS", names);
        if (r == -1)
            return;
        index = r;
        w = list[r];
        if (self hasWc(w))
        {
            self removeWc(w);
            self cacSanitize();
            continue;
        }
        self addWc(w);
    }
}

// Three different streaks, cheapest first; Back keeps the old ones
pickStreaks()
{
    old = [];
    for (n = 1; n <= 3; n++)
    {
        old[n] = self cacGet("ks" + n);
        self.pers["dcac"]["ks" + n] = "none";
    }
    for (n = 1; n <= 3; n++)
    {
        codes = [];
        names = [];
        codes[0] = "none";
        names[0] = "None";
        foreach (ks in level.cac["streak"])
        {
            if (ks == self cacGet("ks1") || ks == self cacGet("ks2"))
                continue;
            codes[codes.size] = ks;
            names[names.size] = cacName(ks) + " (" + level.cac_cost[ks] + ")";
        }
        r = self pickList("Scorestreak " + n, names);
        if (r == -1)
        {
            for (i = 1; i <= 3; i++)
                self.pers["dcac"]["ks" + i] = old[i];
            self cacSave();
            return;
        }
        self.pers["dcac"]["ks" + n] = codes[r];
    }
    self cacSave();
}

applyLoadout()
{
    self cacCleanup();
    self cacSanitize();
    self cacSetOn("1");
    if (self.sessionstate == "playing" && isdefined(self.class))
    {
        self maps\mp\gametypes\_class::giveloadout(self.team, self.class);
        self maps\mp\killstreaks\_killstreaks::giveownedkillstreak();
    }
    self iprintlnbold("^2Loadout applied!");
}

// ---
// Map / Mode (ends the match and loads the pick through the rotation)

// Gametype settings are read every second by _globallogic, so limits change live.
// execgts resets them on every map, so they are re-applied.
applyMatchOptions()
{
    level endon("game_ended");
    wait 1;
    gt = level.gametype;
    if (getdvar("dcac_base_score_" + gt) == "")
        setdvar("dcac_base_score_" + gt, "" + getgametypesetting("scoreLimit"));
    if (getdvar("dcac_opt_timelimit") != "")
        setgametypesetting("timeLimit", getdvarfloat("dcac_opt_timelimit"));
    if (getdvar("dcac_opt_score") != "")
        setgametypesetting("scoreLimit", int(getdvarint("dcac_base_score_" + gt) * getdvarfloat("dcac_opt_score")));
}

matchModes()
{
    m = [];
    m["gt"] = strtok("tdm,dm,dom,conf,sd,koth,hq,ctf,dem,oneflag,gun,oic,shrp,sas", ",");
    m["name"] = strtok("Team Deathmatch,Free-for-All,Domination,Kill Confirmed,Search and Destroy,Hardpoint,Headquarters,Capture the Flag,Demolition,One Flag CTF,Gun Game,One in the Chamber,Sharpshooter,Sticks and Stones", ",");
    return m;
}

// The offline launcher passes the maps found in zone/all as dcac_maps; without it, the base maps
matchMaps()
{
    keys = strtok("mp_la,mp_dockside,mp_carrier,mp_drone,mp_express,mp_hijacked,mp_meltdown,mp_overflow,mp_nightclub,mp_raid,mp_slums,mp_village,mp_turbine,mp_socotra,mp_nuketown_2020,mp_downhill,mp_mirage,mp_hydro,mp_skate,mp_concert,mp_magma,mp_vertigo,mp_studio,mp_uplink,mp_bridge,mp_castaway,mp_paintball,mp_dig,mp_frostbite,mp_pod,mp_takeoff", ",");
    names = strtok("Aftermath,Cargo,Carrier,Drone,Express,Hijacked,Meltdown,Overflow,Plaza,Raid,Slums,Standoff,Turbine,Yemen,Nuketown 2025,Downhill,Mirage,Hydro,Grind,Encore,Magma,Vertigo,Studio,Uplink,Detour,Cove,Rush,Dig,Frost,Pod,Takeoff", ",");
    have = strtok(getdvar("dcac_maps"), ",");
    m = [];
    m["key"] = [];
    m["name"] = [];
    for (i = 0; i < keys.size; i++)
    {
        if (have.size > 0 && !isinarray(have, keys[i]))
            continue;
        if (have.size == 0 && i > 14)
            continue;
        m["key"][m["key"].size] = keys[i];
        m["name"][m["name"].size] = names[i];
    }
    return m;
}

indexOf(list, value)
{
    for (i = 0; i < list.size; i++)
        if (list[i] == value)
            return i;
    return 0;
}

scoreName(mult)
{
    if (mult == "0") return "Unlimited";
    if (mult == "0.5") return "Half";
    if (mult == "2") return "Double";
    return "Default";
}

// Returns true when a new match is loading and the menu closed
openMatchMenu()
{
    modes = matchModes();
    maps = matchMaps();
    mode = indexOf(modes["gt"], level.gametype);
    mapIndex = indexOf(maps["key"], getdvar("mapname"));
    time = getdvar("dcac_opt_timelimit");
    if (time == "") time = "" + getgametypesetting("timeLimit");
    score = getdvar("dcac_opt_score");
    if (score == "") score = "1";
    index = 0;

    for (;;)
    {
        items = [];
        items[0] = "Mode: " + modes["name"][mode];
        items[1] = "Map: " + maps["name"][mapIndex];
        if (time == "0") items[2] = "Time Limit: Unlimited";
        else items[2] = "Time Limit: " + time + " min";
        items[3] = "Score Limit: " + scoreName(score);
        items[4] = "Start Match";
        d = [];
        d[0] = "Which game mode to play next.";
        d[1] = "Which map to play next.";
        d[2] = "How long a match lasts.";
        d[3] = "How many points win the match.";
        d[4] = "Load mode and map. Limits alone apply instantly.";
        self.cac_descs = d;
        self.cac_startIndex = index;
        r = self showMenu("MAP / MODE", items);
        if (r == -1)
            return false;
        index = r;
        switch (r)
        {
            case 0:
                p = self pickList("Mode", modes["name"]);
                if (p != -1) mode = p;
                break;
            case 1:
                p = self pickList("Map", maps["name"]);
                if (p != -1) mapIndex = p;
                break;
            case 2:
                vals = strtok("0,5,10,15,20,30", ",");
                p = self pickList("Time Limit", strtok("Unlimited,5 min,10 min,15 min,20 min,30 min", ","));
                if (p != -1) time = vals[p];
                break;
            case 3:
                // relative to the mode's gamesettings default, captured before any override
                vals = strtok("0,0.5,1,2", ",");
                p = self pickList("Score Limit", strtok("Unlimited,Half,Default,Double", ","));
                if (p != -1) score = vals[p];
                break;
            case 4:
                self startMatch(modes["gt"][mode], modes["name"][mode], maps["key"][mapIndex], maps["name"][mapIndex], time, score);
                return true;
        }
    }
}

startMatch(gt, gtName, map, mapName, time, score)
{
    setdvar("dcac_opt_timelimit", time);
    setdvar("dcac_opt_score", score);
    self cacCleanup();

    if (gt == level.gametype && map == getdvar("mapname"))
    {
        // only the limits changed: apply live, no restart
        level thread applyMatchOptions();
        self iprintlnbold("^2Match settings applied");
        return;
    }

    rot = "execgts " + gt + ".cfg map " + map;
    setdvar("sv_maprotation", rot);
    setdvar("sv_maprotationcurrent", rot);
    iprintlnbold("^2Loading ^7" + mapName + " ^2- ^7" + gtName);
    wait 2;
    exitlevel(0);
}

// ---
// Bot Warfare (BO2 version reads these dvars live; jump & dropshot applies when a bot spawns)

openBotMenu()
{
    index = 0;
    for (;;)
    {
        items = [];
        items[0] = "Bot Count: " + getdvarint("bots_manage_fill");
        items[1] = "Difficulty: " + botSkillName(botSkill());
        if (getdvar("bots_team") == "autoassign" || getdvar("bots_team") == "") items[2] = "Bot Team: Balanced";
        else items[2] = "Bot Team: All Enemies";
        items[3] = "Grenades: " + onOff(getdvarint("bots_play_nade"));
        items[4] = "Jump & Dropshot: " + onOff(getdvarint("bots_play_jumpdrop"));
        d = [];
        d[0] = "How many bots are in the match (0 to 12).";
        d[1] = "How well bots aim, move and react.";
        d[2] = "Balanced: bots on both sides. All Enemies: vs you.";
        d[3] = "Bots throw grenades and equipment.";
        d[4] = "Bots jump and go prone in gunfights (next spawn).";
        self.cac_descs = d;
        self.cac_startIndex = index;
        r = self showMenu("BOT WARFARE", items);
        if (r == -1)
            return;
        index = r;
        switch (r)
        {
            case 0:
                // sv_maxclients is 13 in the LAN config: 12 bots + the player
                counts = strtok("0,2,4,6,8,10,12", ",");
                p = self pickList("Bot Count", counts);
                if (p != -1) setdvar("bots_manage_fill", counts[p]);
                break;
            case 1:
                names = [];
                for (i = 0; i < 4; i++) names[i] = botSkillName(i);
                p = self pickList("Difficulty", names);
                if (p != -1) setdvar("bots_skill", "" + p);
                break;
            case 2:
                if (getdvar("bots_team") == "autoassign" || getdvar("bots_team") == "")
                {
                    // every bot on the team opposite the player
                    if (self.team == "axis") setdvar("bots_team", "allies");
                    else setdvar("bots_team", "axis");
                    setdvar("bots_team_force", "1");
                }
                else
                {
                    setdvar("bots_team", "autoassign");
                    setdvar("bots_team_force", "0");
                }
                break;
            case 3: botToggle("bots_play_nade"); break;
            case 4: botToggle("bots_play_jumpdrop"); break;
        }
    }
}

// Bot Warfare moves bots_skill into bot_difficulty within 1.5s
botSkill()
{
    if (getdvar("bots_skill") != "")
        return getdvarint("bots_skill");
    return getdvarint("bot_difficulty");
}

botSkillName(n)
{
    if (n <= 0) return "Easy";
    if (n == 1) return "Normal";
    if (n == 2) return "Hard";
    return "Veteran";
}

onOff(v)
{
    if (v) return "On";
    return "Off";
}

botToggle(dvar)
{
    if (getdvarint(dvar)) setdvar(dvar, "0");
    else setdvar(dvar, "1");
}

// Bots hold still while anyone has the menu open (BO2 bots have no bots_play_move, so they are frozen)
botsPause()
{
    if (!isdefined(level.dcac_menus))
        level.dcac_menus = 0;
    level.dcac_menus++;
    if (level.dcac_menus == 1)
        level thread botsHold();
}

botsResume()
{
    if (isdefined(level.dcac_menus) && level.dcac_menus > 0)
        level.dcac_menus--;
}

botsHold()
{
    level endon("game_ended");
    while (level.dcac_menus > 0)
    {
        foreach (p in level.players)
            if (p isBotPlayer())
                p freezecontrols(true);
        wait 0.25;
    }
    if (level.inprematchperiod)
        return;
    foreach (p in level.players)
        if (p isBotPlayer())
            p freezecontrols(false);
}

// ---
// HUD menu (MW3 layout: dark left column with title and rows, loadout panel on the right).
// Built once per open; every screen after that only swaps text.

// Distinct setText strings are capped per match; past ~55 new ones, free them all and redraw
cacText(elem, text)
{
    elem.dcac_text = text;
    if (!isdefined(level.dcac_strings[text]))
    {
        level.dcac_strings[text] = true;
        level.dcac_strcount++;
        if (level.dcac_strcount > 55)
        {
            level.dcac_anchor clearalltextafterhudelem();
            level.dcac_strings = [];
            level.dcac_strcount = 0;
            foreach (p in level.players)
                if (isdefined(p.cac_huds))
                    foreach (e in p.cac_huds)
                        if (isdefined(e) && isdefined(e.dcac_text))
                        {
                            level.dcac_strings[e.dcac_text] = true;
                            level.dcac_strcount++;
                            e settext(e.dcac_text);
                        }
        }
    }
    elem settext(text);
}

cacBuildUi()
{
    botsPause();
    self cacLock(true);
    // minimap, score and ammo would sit on top of the menu
    self setclientuivisibilityflag("hud_visible", 0);

    // T6 drops HUD elements past ~23 per player (game's own included), so the panel is three multi-line texts: 17 here.
    // One text was too long: a HUD string past ~255 characters does not draw.
    ui = [];
    all = [];
    // One dark backdrop, no divider (BO2 pause menu look); text uses full-screen x so it keeps its place at any aspect ratio
    all[all.size] = self createBgLocal(0, 0, 640, 480, (0, 0, 0), 0.55, 1);
    ui["title"] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 24, 24, 1.6, "objective", (1, 1, 1), 1, 4);
    cacFullX(ui["title"], 24);
    all[all.size] = ui["title"];
    // vertical position follows the rows (safe area), width follows the left column (full screen)
    ui["hl"] = self createShaderLocal("white", "TOPLEFT", "TOPLEFT", 0, 0, 190, 18, (0.85, 0.45, 0.05), 0.8, 2);
    ui["hl"].horzalign = "fullscreen";
    ui["hl"].x = 0;
    all[all.size] = ui["hl"];
    ui["rows"] = [];
    for (i = 0; i < 10; i++)
    {
        ui["rows"][i] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 28, cacRowY(i), 1.2, "objective", (0.8, 0.8, 0.8), 0, 4);
        cacFullX(ui["rows"][i], 28);
        all[all.size] = ui["rows"][i];
    }
    // 5, 4 and 2 lines of 15 (12 per fontscale 1.0, measured 10-08) with an 8 gap between blocks
    ui["panel"] = [];
    ui["panel"][0] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 380, 60, 1.25, "objective", (1, 1, 1), 1, 4);
    ui["panel"][1] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 380, 60 + 5 * 15 + 8, 1.25, "objective", (1, 1, 1), 1, 4);
    ui["panel"][2] = self createTextLocal("", "TOPLEFT", "TOPLEFT", 380, 60 + 9 * 15 + 16, 1.25, "objective", (1, 1, 1), 1, 4);
    foreach (e in ui["panel"])
    {
        cacFullX(e, 380);
        all[all.size] = e;
    }
    ui["hint"] = self createTextLocal(cacControls(), "TOPLEFT", "TOPLEFT", 380, 350, 1.1, "objective", (0.75, 0.75, 0.75), 1, 4);
    cacFullX(ui["hint"], 380);
    all[all.size] = ui["hint"];

    self.cac_ui = ui;
    self.cac_huds = all;
}

cacFullX(elem, x)
{
    elem.horzalign = "fullscreen";
    elem.x = x;
}

// Freezing the player blocks Dpad and stick input on T6, so only stand still.
// disableweapons() is left out: the Dpad is a weapon switch on T6 and may be swallowed with it.
cacLock(on)
{
    if (on)
    {
        self.cac_speed = self getmovespeedscale();
        self setmovespeedscale(0);
    }
    else
    {
        self setmovespeedscale(self.cac_speed);
        self.cac_speed = undefined;
    }
    self allowjump(!on);
    self allowsprint(!on);
}

cacControls()
{
    return "[{+actionslot 1}]/[{+actionslot 2}] Scroll   [{+gostand}] Select   [{+stance}] Back";
}

cacShowHint(descs, index)
{
    if (isdefined(descs) && isdefined(descs[index]))
        cacText(self.cac_ui["hint"], "^7" + descs[index] + "\n" + cacControls());
    else
        cacText(self.cac_ui["hint"], cacControls());
}

cacRowY(i)
{
    return 78 + (i * 24);
}


cacAttLine(slot)
{
    line = "";
    foreach (k in attKeys(slot))
        if (self cacGet(k) != "none")
        {
            if (line != "") line += " + ";
            line += cacName(self cacGet(k));
        }
    if (line == "") return "No attachments";
    return line;
}

cacCountName(code, n)
{
    if (code != "none" && n == "2")
        return cacName(code) + " x2";
    return cacName(code);
}

cacPerkLine(t)
{
    line = cacName(self cacGet("perk" + t));
    if (self cacGet("perk" + t + "b") != "none")
        line += ", " + cacName(self cacGet("perk" + t + "b"));
    return line;
}

cacUpdatePanel()
{
    wc = "";
    for (i = 1; i <= 3; i++)
        if (self cacGet("wc" + i) != "none")
        {
            if (wc != "") wc += ", ";
            wc += cacName(self cacGet("wc" + i));
        }
    if (wc == "") wc = "None";
    used = self cacPoints();
    pts = "^2" + used;
    if (used > cacMaxPoints()) pts = "^1" + used;
    t = "^3POINTS   " + pts + " ^7/ " + cacMaxPoints() + "\n";
    t += "^3PRIMARY   ^7" + cacName(self cacGet("p")) + "\n";
    t += "      " + self cacAttLine("p") + "\n";
    t += "^3SECONDARY   ^7" + cacName(self cacGet("s")) + "\n";
    t += "      " + self cacAttLine("s");
    cacText(self.cac_ui["panel"][0], t);
    t = "^3EQUIPMENT   ^7" + cacCountName(self cacGet("lethal"), self cacGet("lethal_n")) + " / " + cacCountName(self cacGet("tac"), self cacGet("tac_n")) + "\n";
    t += "^3PERKS   ^7" + self cacPerkLine(1) + "\n";
    t += "      " + self cacPerkLine(2) + "\n";
    t += "      " + self cacPerkLine(3);
    cacText(self.cac_ui["panel"][1], t);
    t = "^3WILDCARDS   ^7" + wc + "\n";
    t += "^3STREAKS   ^7" + cacName(self cacGet("ks1")) + ", " + cacName(self cacGet("ks2")) + ", " + cacName(self cacGet("ks3"));
    cacText(self.cac_ui["panel"][2], t);
}

// self.cac_startIndex / self.cac_descs are one-shot inputs (cursor row, row descriptions)
showMenu(title, items)
{
    self endon("disconnect");
    self endon("death");

    if (!isdefined(self.cac_ui))
        self cacBuildUi();
    ui = self.cac_ui;

    menuSize = items.size;
    if (menuSize > 10) menuSize = 10;

    cacText(ui["title"], title);
    for (i = 0; i < 10; i++)
    {
        if (i < menuSize)
        {
            cacText(ui["rows"][i], items[i]);
            ui["rows"][i].color = (0.8, 0.8, 0.8);
            ui["rows"][i].alpha = 1;
        }
        else
            ui["rows"][i].alpha = 0;
    }
    self cacUpdatePanel();

    index = 0;
    if (isdefined(self.cac_startIndex))
    {
        if (self.cac_startIndex < menuSize) index = self.cac_startIndex;
        self.cac_startIndex = undefined;
    }
    ui["hl"].y = cacRowY(index) - 2;
    if (menuSize > 0) ui["rows"][index].color = (1, 1, 1);
    descs = self.cac_descs;
    self.cac_descs = undefined;
    self cacShowHint(descs, index);

    for (;;)
    {
        command = self waittill_any_return("cac_up", "cac_down", "cac_select", "cac_back");
        if (command == "cac_up" || command == "cac_down")
        {
            if (menuSize == 0)
                continue;
            ui["rows"][index].color = (0.8, 0.8, 0.8);
            if (command == "cac_up") index--;
            else index++;
            if (index < 0) index = menuSize - 1;
            if (index >= menuSize) index = 0;
            ui["hl"].y = cacRowY(index) - 2;
            ui["rows"][index].color = (1, 1, 1);
            self cacShowHint(descs, index);
            self playlocalsound("cac_grid_nav");
        }
        else if (command == "cac_select" && menuSize > 0)
        {
            self playlocalsound("cac_grid_equip_item");
            return index;
        }
        else if (command == "cac_back")
        {
            self playlocalsound("cac_grid_nav");
            return -1;
        }
    }
}

createTextLocal(text, align, relative, x, y, fontscale, font, color, alpha, sort)
{
    elem = self createfontstring(font, fontscale);
    elem.hidewheninmenu = true;
    elem.foreground = true;
    elem.color = color;
    elem.alpha = alpha;
    elem.sort = sort;
    elem setpoint(align, relative, x, y);
    cacText(elem, text);
    return elem;
}

// Full-screen 640x480 space, so columns reach the screen edges at any resolution
createBgLocal(x, y, width, height, color, alpha, sort)
{
    elem = self createShaderLocal("white", "TOPLEFT", "TOPLEFT", 0, 0, width, height, color, alpha, sort);
    elem.horzalign = "fullscreen";
    elem.vertalign = "fullscreen";
    elem.x = x;
    elem.y = y;
    return elem;
}

createShaderLocal(shader, align, relative, x, y, width, height, color, alpha, sort)
{
    elem = self createicon(shader, width, height);
    elem.hidewheninmenu = true;
    elem.foreground = true;
    elem.color = color;
    elem.alpha = alpha;
    elem.sort = sort;
    elem setpoint(align, relative, x, y);
    return elem;
}
