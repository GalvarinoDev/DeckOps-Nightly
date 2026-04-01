-- DeckOps Community Servers - MP Main Menu Mod
-- Adds community server browser, unlock all, and reset stats
-- Built for Plutonium T6 MP
-- Menu technique credit: JezuzLizard (t6-map-templates)

require("T6.CoDBase")
require("T6.Lobby")
require("T6.EdgeShadow")
require("T6.Menus.Playercard")
require("T6.JoinableList")
require("T6.Error")
require("T6.Menus.CODTv")
require("T6.Menus.SignOutPopup")
require("T6.Menus.RejoinSessionPopup")
require("T6.Mods")
if CoD.isWIIU then
	require("T6.WiiUControllerSettings")
end
if CoD.isZombie == false and (CoD.isXBOX or CoD.isPS3) then
	require("T6.Menus.EliteAppPopup")
end

CoD.MainLobby = {}

-- ============================================================
-- DeckOps Server List
-- Add or remove servers here. Each entry needs a display name
-- and the connect command (ip:port).
-- ============================================================
CoD.DeckOps = {}
CoD.DeckOps.Servers = {
	{ name = "BO2 Multiplayer", command = "connect 207.244.231.63:4976" },
	-- Future servers go here:
	-- { name = "BO2 Multiplayer #2", command = "connect x.x.x.x:port" },
}

-- ============================================================
-- DeckOps Server List Popup
-- ============================================================
CoD.DeckOps.OpenServerList = function(MainLobbyWidget, ClientInstance)
	local popup = MainLobbyWidget:openPopup("DeckOpsServerSelect", ClientInstance.controller)
end

CoD.DeckOps.ConnectToServer = function(MainLobbyWidget, ClientInstance, connectCmd)
	Engine.Exec(ClientInstance.controller, connectCmd)
end

CoD.DeckOps.UnlockAll = function(MainLobbyWidget, ClientInstance)
	Engine.Exec(ClientInstance.controller, "unlockall")
	local popup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
	popup:setMessage("Everything unlocked! Restart the game for changes to take effect.")
	popup.anyControllerAllowed = true
end

CoD.DeckOps.ResetStatsConfirm = function(MainLobbyWidget, ClientInstance)
	local popup = MainLobbyWidget:openPopup("DeckOpsResetConfirm", ClientInstance.controller)
end

CoD.DeckOps.DoResetStats = function(MainLobbyWidget, ClientInstance)
	Engine.Exec(ClientInstance.controller, "resetStats")
	local popup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
	popup:setMessage("Stats have been reset. Restart the game for changes to take effect.")
	popup.anyControllerAllowed = true
end

-- ============================================================
-- Server Select Popup
-- ============================================================
LUI.createMenu.DeckOpsServerSelect = function(LocalClientIndex)
	local widget = LUI.UIElement.new()
	widget:setLeftRight(true, true, 0, 0)
	widget:setTopBottom(true, true, 0, 0)
	widget.id = "DeckOpsServerSelect"
	widget.anyControllerAllowed = true

	-- Dark background overlay
	local overlay = LUI.UIImage.new()
	overlay:setLeftRight(true, true, 0, 0)
	overlay:setTopBottom(true, true, 0, 0)
	overlay:setRGB(0, 0, 0)
	overlay:setAlpha(0.7)
	widget:addElement(overlay)

	-- Title text
	local title = LUI.UIText.new()
	title:setLeftRight(true, true, 0, 0)
	title:setTopBottom(true, false, 160, 195)
	title:setFont(CoD.fonts.Big)
	title:setText("DECKOPS COMMUNITY SERVERS")
	title:setAlignment(LUI.Alignment.Center)
	title:setRGB(0.9, 0.9, 0.9)
	widget:addElement(title)

	-- Server buttons
	local yOffset = 220
	local buttonHeight = 40
	local buttonSpacing = 10

	for i, server in ipairs(CoD.DeckOps.Servers) do
		local btn = CoD.CoD9Button.new(widget, LocalClientIndex, {
			leftAnchor = true,
			rightAnchor = true,
			left = 200,
			right = -200,
			topAnchor = true,
			bottomAnchor = false,
			top = yOffset,
			bottom = yOffset + buttonHeight
		})
		btn:setText(server.name)
		btn.hintText = "Connect to " .. server.name
		local serverCmd = server.command
		btn:registerEventHandler("button_action", function(element, event)
			Engine.Exec(event.controller or LocalClientIndex, serverCmd)
			widget:close()
		end)
		widget:addElement(btn)
		yOffset = yOffset + buttonHeight + buttonSpacing
	end

	-- Cancel / Back text
	local cancelText = LUI.UIText.new()
	cancelText:setLeftRight(true, true, 0, 0)
	cancelText:setTopBottom(true, false, yOffset + 20, yOffset + 45)
	cancelText:setFont(CoD.fonts.Small)
	cancelText:setText("Press B / ESC to go back")
	cancelText:setAlignment(LUI.Alignment.Center)
	cancelText:setRGB(0.6, 0.6, 0.6)
	widget:addElement(cancelText)

	-- Handle back button
	widget:registerEventHandler("button_prompt_back", function(element, event)
		widget:close()
	end)

	-- Handle B button / Escape
	widget:registerEventHandler("button_secondary", function(element, event)
		widget:close()
	end)

	if CoD.useController then
		-- Focus the first server button for controller navigation
		widget:processEvent({ name = "gain_focus" })
	end

	return widget
end

-- ============================================================
-- Reset Stats Confirmation Popup
-- ============================================================
LUI.createMenu.DeckOpsResetConfirm = function(LocalClientIndex)
	local widget = LUI.UIElement.new()
	widget:setLeftRight(true, true, 0, 0)
	widget:setTopBottom(true, true, 0, 0)
	widget.id = "DeckOpsResetConfirm"
	widget.anyControllerAllowed = true

	-- Dark background overlay
	local overlay = LUI.UIImage.new()
	overlay:setLeftRight(true, true, 0, 0)
	overlay:setTopBottom(true, true, 0, 0)
	overlay:setRGB(0, 0, 0)
	overlay:setAlpha(0.7)
	widget:addElement(overlay)

	-- Warning text
	local warning = LUI.UIText.new()
	warning:setLeftRight(true, true, 0, 0)
	warning:setTopBottom(true, false, 200, 235)
	warning:setFont(CoD.fonts.Big)
	warning:setText("RESET ALL STATS?")
	warning:setAlignment(LUI.Alignment.Center)
	warning:setRGB(1, 0.3, 0.3)
	widget:addElement(warning)

	local detail = LUI.UIText.new()
	detail:setLeftRight(true, true, 0, 0)
	detail:setTopBottom(true, false, 245, 270)
	detail:setFont(CoD.fonts.Small)
	detail:setText("This will reset all stats and rank. This cannot be undone.")
	detail:setAlignment(LUI.Alignment.Center)
	detail:setRGB(0.8, 0.8, 0.8)
	widget:addElement(detail)

	-- Confirm button
	local confirmBtn = CoD.CoD9Button.new(widget, LocalClientIndex, {
		leftAnchor = true,
		rightAnchor = true,
		left = 250,
		right = -250,
		topAnchor = true,
		bottomAnchor = false,
		top = 300,
		bottom = 340
	})
	confirmBtn:setText("YES, RESET MY STATS")
	confirmBtn:registerEventHandler("button_action", function(element, event)
		widget:close()
		Engine.Exec(event.controller or LocalClientIndex, "resetStats")
		-- Reopen the main lobby to show confirmation
		local mainLobby = LUI.FlowManager.GetMenuScopedUsingElement(widget)
		if mainLobby then
			local popup = mainLobby:openPopup("Error", event.controller or LocalClientIndex)
			popup:setMessage("Stats have been reset. Restart the game for changes to take effect.")
			popup.anyControllerAllowed = true
		end
	end)
	widget:addElement(confirmBtn)

	-- Cancel button
	local cancelBtn = CoD.CoD9Button.new(widget, LocalClientIndex, {
		leftAnchor = true,
		rightAnchor = true,
		left = 250,
		right = -250,
		topAnchor = true,
		bottomAnchor = false,
		top = 350,
		bottom = 390
	})
	cancelBtn:setText("CANCEL")
	cancelBtn:registerEventHandler("button_action", function(element, event)
		widget:close()
	end)
	widget:addElement(cancelBtn)

	-- Handle B button / Escape
	widget:registerEventHandler("button_prompt_back", function(element, event)
		widget:close()
	end)

	widget:registerEventHandler("button_secondary", function(element, event)
		widget:close()
	end)

	return widget
end

-- ============================================================
-- Original MainLobby functions (from base game)
-- Only the button population functions are modified.
-- Everything else is preserved as the game expects it.
-- ============================================================

CoD.MainLobby.ShouldPreventCreateLobby = function()
	if UIExpression.AcceptingInvite() == 1 or Engine.IsJoiningAnotherParty() == 1 or UIExpression.PrivatePartyHost() == 0 or Engine.IsGameLobbyRunning() then
		return true
	else
		return false
	end
end

CoD.MainLobby.OnlinePlayAvailable = function(MainLobbyWidget, ClientInstance, Boolean)
	if Boolean == nil then
		Boolean = false
	end
	if CoD.isPC and Engine.IsVacBanned() then
		local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
		ErrorPopup:setMessage(Engine.Localize("PLATFORM_VACBANNED"))
		ErrorPopup.anyControllerAllowed = true
		ErrorPopup.callingMenu = MainLobbyWidget
		return 0
	elseif CoD.isWIIU and Engine.IsSignedInToDemonware(ClientInstance.controller) == false then
		if UIExpression.IsPrimaryLocalClient(ClientInstance.controller) == 1 then
			Engine.Exec(ClientInstance.controller, "xsigninlive")
		end
		return 0
	elseif UIExpression.IsGuest(ClientInstance.controller) == 1 then
		local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
		ErrorPopup:setMessage(Engine.Localize("XBOXLIVE_NOGUESTACCOUNTS"))
		ErrorPopup.anyControllerAllowed = true
	elseif UIExpression.DvarBool(ClientInstance.controller, "live_betaexpired") == 1 then
		local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
		ErrorPopup:setMessage(Engine.Localize("MP_BETACLOSED"))
	elseif UIExpression.IsSignedInToLive(ClientInstance.controller) == 0 then
		if CoD.isPS3 or CoD.isWIIU then
			if UIExpression.IsPrimaryLocalClient(ClientInstance.controller) == 1 then
				Engine.Exec(ClientInstance.controller, "xsigninlive")
			else
				Engine.Exec(ClientInstance.controller, "signclientin")
			end
		elseif CoD.isPC then
			if 0 == UIExpression.GetUsedControllerCount() then
				Engine.Exec(ClientInstance.controller, "xsigninlivenoguests")
			else
				Engine.Exec(ClientInstance.controller, "xsigninlive")
			end
		elseif 0 == UIExpression.GetUsedControllerCount() then
			Engine.Exec(ClientInstance.controller, "xsigninlivenoguests")
		elseif UIExpression.IsSignedIn(ClientInstance.controller) == 1 then
			MainLobbyWidget:openPopup("popup_signintolive", ClientInstance.controller)
		else
			Engine.Exec(ClientInstance.controller, "xsigninlive")
		end
	elseif (UIExpression.IsContentRatingAllowed(ClientInstance.controller) == 0 or UIExpression.IsAnyControllerMPRestricted() == 1) and not Boolean then
		local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
		ErrorPopup:setMessage(Engine.Localize("XBOXLIVE_MPNOTALLOWED"))
		ErrorPopup.anyControllerAllowed = true
	elseif UIExpression.IsDemonwareFetchingDone(ClientInstance.controller) == 1 then
		local PlayerStatTable1 = Engine.GetPlayerStats(ClientInstance.controller)
		local PlayerStatTable2 = Engine.GetPlayerStats(ClientInstance.controller)
		if PlayerStatTable1.cacLoadouts.resetWarningDisplayed:get() == 0 then
			PlayerStatTable1.cacLoadouts.resetWarningDisplayed:set(1)
			if PlayerStatTable2.cacLoadouts.classWarningDisplayed ~= nil then
				PlayerStatTable2.cacLoadouts.classWarningDisplayed:set(1)
			end
			local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
			ErrorPopup:setMessage(Engine.Localize("MENU_STATS_RESET"))
			ErrorPopup.anyControllerAllowed = true
		elseif CoD.isZombie == false and PlayerStatTable2.cacLoadouts.classWarningDisplayed:get() == 0 then
			PlayerStatTable2.cacLoadouts.classWarningDisplayed:set(1)
			local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
			ErrorPopup:setMessage(Engine.Localize("MENU_RESETCUSTOMCLASSES"))
			ErrorPopup.anyControllerAllowed = true
		else
			return 1
		end
	else
		Engine.ExecNow(nil, "initiatedemonwareconnect")
		local ConnectingDemonwarePopup = MainLobbyWidget:openPopup("popup_connectingdw", ClientInstance.controller)
		ConnectingDemonwarePopup.openingStore = Boolean
		ConnectingDemonwarePopup.callingMenu = MainLobbyWidget
	end
	return 0
end

CoD.MainLobby.IsControllerCountValid = function(MainLobbyWidget, LocalClientIndex, MaxLocalPlayers)
	if MaxLocalPlayers < UIExpression.GetUsedControllerCount() then
		local ErrorPopup = MainLobbyWidget:openPopup("Error", LocalClientIndex)
		ErrorPopup:setMessage(Engine.Localize("XBOXLIVE_TOOMANYCONTROLLERS"))
		ErrorPopup.anyControllerAllowed = true
		return 0
	else
		return 1
	end
end

CoD.MainLobby.OpenPlayerMatchPartyLobby = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 then
		Engine.ProbationCheckForDashboardWarning(CoD.GAMEMODE_PUBLIC_MATCH)
		local InProbation, LocalClientIndexInProbation = Engine.ProbationCheckInProbation(CoD.GAMEMODE_PUBLIC_MATCH)
		if InProbation == true then
			MainLobbyWidget:openPopup("popup_public_inprobation", LocalClientIndexInProbation)
			return
		end
		local GivenProbation, LocalClientIndexGivenProbation = Engine.ProbationCheckForProbation(CoD.GAMEMODE_PUBLIC_MATCH)
		if GivenProbation == true then
			MainLobbyWidget:openPopup("popup_public_givenprobation", LocalClientIndexGivenProbation)
			return
		elseif Engine.ProbationCheckParty(CoD.GAMEMODE_PUBLIC_MATCH, ClientInstance.controller) == true then
			MainLobbyWidget:openPopup("popup_public_partyprobation", ClientInstance.controller)
			return
		end
		local MaxLocalPlayers = UIExpression.DvarInt(LocalClientIndexGivenProbation, "party_maxlocalplayers_playermatch")
		if CoD.MainLobby.IsControllerCountValid(MainLobbyWidget, ClientInstance.controller, MaxLocalPlayers) == 1 then
			MainLobbyWidget.lobbyPane.body.lobbyList.maxLocalPlayers = MaxLocalPlayers
			CoD.SwitchToPlayerMatchLobby(ClientInstance.controller)
			if CoD.isZombie == true then
				Engine.PartyHostSetUIState(CoD.PARTYHOST_STATE_SELECTING_PLAYLIST)
				CoD.PlaylistCategoryFilter = "playermatch"
				MainLobbyWidget:openMenu("SelectMapZM", ClientInstance.controller)
				CoD.GameGlobeZombie.MoveToCenter(ClientInstance.controller)
			else
				MainLobbyWidget:openMenu("PlayerMatchPartyLobby", ClientInstance.controller)
			end
			MainLobbyWidget:close()
		end
	end
end

CoD.MainLobby.OpenLeagueSelectionPopup = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 then
		Engine.ProbationCheckForDashboardWarning(CoD.GAMEMODE_PUBLIC_MATCH)
		local InProbation, LocalClientIndexInProbation = Engine.ProbationCheckInProbation(CoD.GAMEMODE_LEAGUE_MATCH)
		if InProbation == true then
			MainLobbyWidget:openPopup("popup_league_inprobation", LocalClientIndexInProbation)
			return
		end
		local GivenProbation, LocalClientIndexGivenProbation = Engine.ProbationCheckForProbation(CoD.GAMEMODE_LEAGUE_MATCH)
		if GivenProbation == true then
			MainLobbyWidget:openPopup("popup_league_givenprobation", LocalClientIndexGivenProbation)
			return
		elseif Engine.ProbationCheckParty(CoD.GAMEMODE_LEAGUE_MATCH, ClientInstance.controller) == true then
			MainLobbyWidget:openPopup("popup_league_partyprobation", ClientInstance.controller)
			return
		end
		Engine.PartyHostSetUIState(CoD.PARTYHOST_STATE_SELECTING_PLAYLIST)
		CoD.PlaylistCategoryFilter = "leaguematch"
		PlaylistPopup = MainLobbyWidget:openPopup("PlaylistSelection", ClientInstance.controller)
		PlaylistPopup:addCategoryButtons(ClientInstance.controller)
		Engine.PlaySound("cac_screen_fade")
	end
end

CoD.MainLobby.OpenLeaguePlayPartyLobby = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 then
		local MaxLocalPlayers = UIExpression.DvarInt(ClientInstance.controller, "party_maxlocalplayers_playermatch")
		if CoD.MainLobby.IsControllerCountValid(MainLobbyWidget, ClientInstance.controller, MaxLocalPlayers) == 1 then
			MainLobbyWidget.lobbyPane.body.lobbyList.maxLocalPlayers = MaxLocalPlayers
			CoD.SwitchToLeagueMatchLobby(ClientInstance.controller)
			MainLobbyWidget:openMenu("LeaguePlayPartyLobby", ClientInstance.controller)
			MainLobbyWidget:close()
		end
	end
end

CoD.MainLobby.OpenCustomGamesLobby = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 and CoD.MainLobby.IsControllerCountValid(MainLobbyWidget, ClientInstance.controller, UIExpression.DvarInt(ClientInstance.controller, "party_maxlocalplayers_privatematch")) == 1 then
		CoD.SwitchToPrivateLobby(ClientInstance.controller)
		if CoD.isZombie == true then
			Engine.SetDvar("ui_zm_mapstartlocation", "")
			MainLobbyWidget:openMenu("SelectMapZM", ClientInstance.controller)
			CoD.GameGlobeZombie.MoveToCenter(ClientInstance.controller)
		else
			MainLobbyWidget:openMenu("PrivateOnlineGameLobby", ClientInstance.controller)
		end
		MainLobbyWidget:close()
	end
end

CoD.MainLobby.OpenSoloLobby_Zombie = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 then
		if CoD.MainLobby.IsControllerCountValid(MainLobbyWidget, ClientInstance.controller, 1) == 1 then
			MainLobbyWidget.lobbyPane.body.lobbyList.maxLocalPlayers = 1
			CoD.SwitchToPlayerMatchLobby(ClientInstance.controller)
			Engine.PartyHostSetUIState(CoD.PARTYHOST_STATE_SELECTING_PLAYLIST)
			Dvar.party_maxplayers:set(1)
			CoD.PlaylistCategoryFilter = CoD.Zombie.PLAYLIST_CATEGORY_FILTER_SOLOMATCH
			MainLobbyWidget:openMenu("SelectMapZM", ClientInstance.controller)
			CoD.GameGlobeZombie.MoveToCenter(ClientInstance.controller)
			MainLobbyWidget:close()
		end
	end
end

CoD.MainLobby.OpenTheaterLobby = function(MainLobbyWidget, ClientInstance)
	if CoD.MainLobby.ShouldPreventCreateLobby() then
		return
	elseif UIExpression.CanSwitchToLobby(ClientInstance.controller, Dvar.party_maxplayers_theater:get(), Dvar.party_maxlocalplayers_theater:get()) == 0 then
		Dvar.ui_errorTitle:set(Engine.Localize("MENU_NOTICE_CAPS"))
		Dvar.ui_errorMessage:set(Engine.Localize("MENU_FILESHARE_MAX_LOCAL_PLAYERS"))
		CoD.Menu.OpenErrorPopup(MainLobbyWidget, {
			controller = ClientInstance.controller
		})
		return
	elseif Engine.CanViewContent() == false then
		MainLobbyWidget:openPopup("popup_contentrestricted", ClientInstance.controller)
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 and CoD.MainLobby.IsControllerCountValid(MainLobbyWidget, ClientInstance.controller, UIExpression.DvarInt(ClientInstance.controller, "party_maxlocalplayers_theater")) == 1 then
		CoD.SwitchToTheaterLobby(ClientInstance.controller)
		MainLobbyWidget:openMenu("TheaterLobby", ClientInstance.controller, {
			parent = "MainLobby"
		})
		MainLobbyWidget:close()
	end
end

CoD.MainLobby.OpenCODTV = function(MainLobbyWidget, ClientInstance)
	if Engine.CanViewContent() == false then
		MainLobbyWidget:openPopup("popup_contentrestricted", ClientInstance.controller)
		return
	elseif Engine.IsLivestreamEnabled() then
		MainLobbyWidget:openPopup("CODTv_Error", ClientInstance.controller)
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 and Engine.IsCodtvContentLoaded() == true then
		CoD.perController[ClientInstance.controller].codtvRoot = "community"
		MainLobbyWidget:openPopup("CODTv", ClientInstance.controller)
	end
end

CoD.MainLobby.OpenBarracks = function(MainLobbyWidget, ClientInstance)
	if UIExpression.IsGuest(ClientInstance.controller) == 1 then
		MainLobbyWidget:openPopup("popup_guest_contentrestricted", ClientInstance.controller)
		return
	elseif CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance) == 1 then
		if CoD.isZombie == true then
			Engine.Exec(ClientInstance.controller, "party_setHostUIString ZMUI_VIEWING_LEADERBOARD")
			MainLobbyWidget:openPopup("LeaderboardCarouselZM", ClientInstance.controller)
		else
			Engine.Exec(ClientInstance.controller, "party_setHostUIString MENU_VIEWING_PLAYERCARD")
			MainLobbyWidget:openPopup("Barracks", ClientInstance.controller)
		end
	end
end

CoD.MainLobby.OpenStore = function(MainLobbyWidget, ClientInstance)
	if MainLobbyWidget.occludedBy then
		return
	end
	Engine.SetDvar("ui_openStoreForMTX", 0)
	if Engine.CheckNetConnection() == false then
		local NetConnectionCheckPopup = MainLobbyWidget:openPopup("popup_net_connection_store", ClientInstance.controller)
		NetConnectionCheckPopup.callingMenu = MainLobbyWidget
		return
	end
	Engine.Exec(ClientInstance.controller, "setclientbeingusedandprimary")
	if CoD.MainLobby.OnlinePlayAvailable(MainLobbyWidget, ClientInstance, true) == 1 then
		if not CoD.isPS3 or UIExpression.IsSubUser(ClientInstance.controller) ~= 1 then
			Dvar.ui_storeButtonPressed:set(true)
			CoD.perController[ClientInstance.controller].codtvRoot = "ingamestore"
			if CoD.isPC then
				Engine.ShowMarketplaceUI(ClientInstance.controller)
			else
				MainLobbyWidget:openPopup("CODTv", ClientInstance.controller)
			end
		else
			local ErrorPopup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
			ErrorPopup:setMessage(Engine.Localize("MENU_SUBUSERS_NOTALLOWED"))
			ErrorPopup.anyControllerAllowed = true
		end
	end
end

CoD.MainLobby.OpenControlsMenu = function(MainLobbyWidget, ClientInstance)
	MainLobbyWidget:openPopup("WiiUControllerSettings", ClientInstance.controller, true)
end

CoD.MainLobby.OpenOptionsMenu = function(MainLobbyWidget, ClientInstance)
	MainLobbyWidget:openPopup("OptionsMenu", ClientInstance.controller)
end

-- ============================================================
-- Button Visibility (controls which buttons show based on state)
-- ============================================================

CoD.MainLobby.UpdateButtonPaneButtonVisibilty_Multiplayer = function(MainLobbyButtonPane)
	if CoD.isPartyHost() then
		-- DeckOps servers button (replaces matchmaking position)
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.deckopsServersButton)
		if not Engine.IsBetaBuild() then
			MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.customGamesButton)
		end
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.theaterButton)
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.postTheaterSpacer)
	else
		MainLobbyButtonPane.body.deckopsServersButton:closeAndRefocus(MainLobbyButtonPane.body.barracksButton)
		if not Engine.IsBetaBuild() then
			MainLobbyButtonPane.body.customGamesButton:closeAndRefocus(MainLobbyButtonPane.body.barracksButton)
		end
		MainLobbyButtonPane.body.theaterButton:closeAndRefocus(MainLobbyButtonPane.body.barracksButton)
		MainLobbyButtonPane.body.postTheaterSpacer:closeAndRefocus(MainLobbyButtonPane.body.barracksButton)
		MainLobbyButtonPane.body.serverBrowserButton:closeAndRefocus(MainLobbyButtonPane.body.serverBrowserButton)
	end
end

CoD.MainLobby.UpdateButtonPaneButtonVisibilty_Zombie = function(MainLobbyButtonPane)
	if CoD.isPartyHost() then
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.customSpacer)
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.customGamesButton)
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.theaterSpacer)
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.theaterButton)
		if UIExpression.DvarInt(nil, "party_playerCount") <= 1 then
			MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.soloPlayButton)
		else
			MainLobbyButtonPane.body.soloPlayButton:closeAndRefocus(MainLobbyButtonPane.body.theaterButton)
		end
		MainLobbyButtonPane.body.buttonList:addElement(MainLobbyButtonPane.body.optionSpacer)
	else
		MainLobbyButtonPane.body.soloPlayButton:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.customSpacer:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.customGamesButton:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.theaterButton:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.theaterSpacer:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.optionSpacer:closeAndRefocus(MainLobbyButtonPane.body.optionsButton)
		MainLobbyButtonPane.body.serverBrowserButton:closeAndRefocus(MainLobbyButtonPane.body.serverBrowserButton)
	end
end

CoD.MainLobby.UpdateButtonPaneButtonVisibilty = function(MainLobbyButtonPane)
	if MainLobbyButtonPane == nil or MainLobbyButtonPane.body == nil then
		return
	elseif CoD.isZombie == true then
		CoD.MainLobby.UpdateButtonPaneButtonVisibilty_Zombie(MainLobbyButtonPane)
	else
		CoD.MainLobby.UpdateButtonPaneButtonVisibilty_Multiplayer(MainLobbyButtonPane)
	end
	MainLobbyButtonPane:setLayoutCached(false)
end

CoD.MainLobby.UpdateButtonPromptVisibility = function(MainLobbyWidget)
	if MainLobbyWidget == nil then
		return
	end
	MainLobbyWidget:removeBackButton()
	local ShouldAddJoinButton = false
	if MainLobbyWidget.joinButton ~= nil then
		MainLobbyWidget.joinButton:close()
		ShouldAddJoinButton = true
	end
	MainLobbyWidget.friendsButton:close()
	if MainLobbyWidget.partyPrivacyButton ~= nil then
		MainLobbyWidget.partyPrivacyButton:close()
	end
	MainLobbyWidget:addBackButton()
	MainLobbyWidget:addFriendsButton()
	if ShouldAddJoinButton then
		MainLobbyWidget:addJoinButton()
	end
	if MainLobbyWidget.panelManager.slidingEnabled ~= true then
		MainLobbyWidget.friendsButton:disable()
	end
	if MainLobbyWidget.panelManager:isPanelOnscreen("buttonPane") then
		MainLobbyWidget:addPartyPrivacyButton()
	end
	MainLobbyWidget:addNATType()
end

-- ============================================================
-- Button Population - MP (modified for DeckOps)
-- ============================================================

CoD.MainLobby.PopulateButtons_Multiplayer = function(MainLobbyButtonPane)
	-- DeckOps Servers button (replaces Public Match / Matchmaking)
	MainLobbyButtonPane.body.deckopsServersButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("DECKOPS SERVERS"), nil, 1)
	MainLobbyButtonPane.body.deckopsServersButton.hintText = "Browse and join DeckOps community servers"
	MainLobbyButtonPane.body.deckopsServersButton:setActionEventName("deckops_open_servers")

	-- Server Browser (Plutonium's built-in)
	MainLobbyButtonPane.body.serverBrowserButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("SERVER BROWSER"), nil, 2)
	MainLobbyButtonPane.body.serverBrowserButton.hintText = Engine.Localize(CoD.MPZM("MPUI_PLAYER_MATCH_DESC", "ZMUI_PLAYER_MATCH_DESC"))
	MainLobbyButtonPane.body.serverBrowserButton:setActionEventName("open_server_browser_mainlobby")
	CoD.SetupMatchmakingLock(MainLobbyButtonPane.body.serverBrowserButton)

	-- Custom Games
	if not Engine.IsBetaBuild() then
		MainLobbyButtonPane.body.customGamesButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_CUSTOMGAMES_CAPS"), nil, 3)
		MainLobbyButtonPane.body.customGamesButton.hintText = Engine.Localize(CoD.MPZM("MPUI_CUSTOM_MATCH_DESC", "ZMUI_CUSTOM_MATCH_DESC"))
		MainLobbyButtonPane.body.customGamesButton:setActionEventName("open_custom_games_lobby")
		CoD.SetupCustomGamesLock(MainLobbyButtonPane.body.customGamesButton)
	end

	-- Theater
	MainLobbyButtonPane.body.theaterButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_THEATER_CAPS"), nil, 4)
	MainLobbyButtonPane.body.theaterButton:setActionEventName("open_theater_lobby")
	MainLobbyButtonPane.body.theaterButton.hintText = Engine.Localize(CoD.MPZM("MPUI_THEATER_DESC", "ZMUI_THEATER_DESC"))
	MainLobbyButtonPane.body.postTheaterSpacer = MainLobbyButtonPane.body.buttonList:addSpacer(CoD.CoD9Button.Height / 2, 5)

	-- Barracks
	if not Engine.IsBetaBuild() then
		MainLobbyButtonPane.body.barracksButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_BARRACKS_CAPS"), nil, 6)
		MainLobbyButtonPane.body.barracksButton.id = "CoD9Button" .. "." .. "MainLobby" .. "." .. Engine.Localize("MENU_BARRACKS_CAPS")
		CoD.SetupBarracksLock(MainLobbyButtonPane.body.barracksButton)
		CoD.SetupBarracksNew(MainLobbyButtonPane.body.barracksButton)
		MainLobbyButtonPane.body.barracksButton:setActionEventName("open_barracks")
	end

	-- Unlock All (under Barracks)
	MainLobbyButtonPane.body.unlockAllButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("UNLOCK ALL"), nil, 7)
	MainLobbyButtonPane.body.unlockAllButton.hintText = "Unlock all weapons, perks, and equipment"
	MainLobbyButtonPane.body.unlockAllButton:setActionEventName("deckops_unlock_all")

	-- Reset Stats (under Unlock All)
	MainLobbyButtonPane.body.resetStatsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("RESET STATS"), nil, 8)
	MainLobbyButtonPane.body.resetStatsButton.hintText = "Reset all stats and rank to level 1"
	MainLobbyButtonPane.body.resetStatsButton:setActionEventName("deckops_reset_stats")

	-- Elite App (console only)
	if CoD.isZombie == false and not Engine.IsBetaBuild() and (CoD.isXBOX or CoD.isPS3) and Engine.IsEliteAvailable() and Engine.IsEliteButtonAvailable() then
		MainLobbyButtonPane.body.eliteAppButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_ELITE_CAPS"), nil, 9)
		MainLobbyButtonPane.body.eliteAppButton.hintText = Engine.Localize("MENU_ELITE_DESC")
		MainLobbyButtonPane.body.eliteAppButton:setActionEventName("open_eliteapp_popup")
	end

	MainLobbyButtonPane.body.buttonList:addSpacer(CoD.CoD9Button.Height / 2, 10)

	-- Options
	MainLobbyButtonPane.body.optionsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_OPTIONS_CAPS"), nil, 11)
	MainLobbyButtonPane.body.optionsButton.hintText = Engine.Localize("MPUI_OPTIONS_DESC")
	MainLobbyButtonPane.body.optionsButton:setActionEventName("open_options_menu")

	-- Mods
	MainLobbyButtonPane.body.modsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MODS"), nil, 12)
	MainLobbyButtonPane.body.modsButton:setActionEventName("open_mods_menu")
end

-- ============================================================
-- Button Population - ZM (unchanged from base Plutonium)
-- ============================================================

CoD.MainLobby.PopulateButtons_Zombie = function(MainLobbyButtonPane)
	MainLobbyButtonPane.body.serverBrowserButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("SERVER BROWSER"), nil, 1)
	MainLobbyButtonPane.body.serverBrowserButton.hintText = Engine.Localize(CoD.MPZM("MPUI_PLAYER_MATCH_DESC", "ZMUI_PLAYER_MATCH_DESC"))
	MainLobbyButtonPane.body.serverBrowserButton:setActionEventName("open_server_browser_mainlobby")
	CoD.SetupMatchmakingLock(MainLobbyButtonPane.body.serverBrowserButton)

	MainLobbyButtonPane.body.soloPlayButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("ZMUI_SOLO_PLAY_CAPS"), nil, 2)
	MainLobbyButtonPane.body.soloPlayButton.hintText = Engine.Localize("ZMUI_SOLO_PLAY_DESC")
	MainLobbyButtonPane.body.soloPlayButton:setActionEventName("open_solo_lobby_zombie")

	MainLobbyButtonPane.body.customSpacer = MainLobbyButtonPane.body.buttonList:addSpacer(CoD.CoD9Button.Height / 2, 3)
	MainLobbyButtonPane.body.customGamesButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_CUSTOMGAMES_CAPS"), nil, 4)
	MainLobbyButtonPane.body.customGamesButton.hintText = Engine.Localize(CoD.MPZM("MPUI_CUSTOM_MATCH_DESC", "ZMUI_CUSTOM_MATCH_DESC"))
	MainLobbyButtonPane.body.customGamesButton:setActionEventName("open_custom_games_lobby")
	CoD.SetupCustomGamesLock(MainLobbyButtonPane.body.customGamesButton)

	MainLobbyButtonPane.body.theaterButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_THEATER_CAPS"), nil, 5)
	MainLobbyButtonPane.body.theaterButton:setActionEventName("open_theater_lobby")
	MainLobbyButtonPane.body.theaterButton.hintText = Engine.Localize(CoD.MPZM("MPUI_THEATER_DESC", "ZMUI_THEATER_DESC"))
	MainLobbyButtonPane.body.theaterSpacer = MainLobbyButtonPane.body.buttonList:addSpacer(CoD.CoD9Button.Height / 2, 6)

	MainLobbyButtonPane.body.barracksButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MPUI_LEADERBOARDS_CAPS"), nil, 7)
	CoD.SetupBarracksLock(MainLobbyButtonPane.body.barracksButton)
	MainLobbyButtonPane.body.barracksButton:setActionEventName("open_barracks")

	MainLobbyButtonPane.body.optionSpacer = MainLobbyButtonPane.body.buttonList:addSpacer(CoD.CoD9Button.Height / 2, 8)
	MainLobbyButtonPane.body.optionsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_OPTIONS_CAPS"), nil, 9)
	MainLobbyButtonPane.body.optionsButton.hintText = Engine.Localize("MPUI_OPTIONS_DESC")
	MainLobbyButtonPane.body.optionsButton:setActionEventName("open_options_menu")
	MainLobbyButtonPane.body.modsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MODS"), nil, 10)
	MainLobbyButtonPane.body.modsButton:setActionEventName("open_mods_menu")
end

CoD.MainLobby.PopulateButtons = function(MainLobbyButtonPane)
	if CoD.isZombie == true then
		CoD.MainLobby.PopulateButtons_Zombie(MainLobbyButtonPane)
	else
		CoD.MainLobby.PopulateButtons_Multiplayer(MainLobbyButtonPane)
	end
	if CoD.isWIIU then
		MainLobbyButtonPane.body.controlsButton = MainLobbyButtonPane.body.buttonList:addButton(Engine.Localize("MENU_CONTROLLER_SETTINGS_CAPS"), nil, 9)
		MainLobbyButtonPane.body.controlsButton.hintText = Engine.Localize("MENU_CONTROLLER_SETTINGS_DESC")
		MainLobbyButtonPane.body.controlsButton:setActionEventName("open_controls_menu")
	end
	if CoD.isOnlineGame() then
		if MainLobbyButtonPane.playerCountLabel == nil then
			MainLobbyButtonPane.playerCountLabel = LUI.UIText.new()
			MainLobbyButtonPane:addElement(MainLobbyButtonPane.playerCountLabel)
		end
		MainLobbyButtonPane.playerCountLabel:setLeftRight(true, false, 0, 0)
		MainLobbyButtonPane.playerCountLabel:setTopBottom(false, true, -30 - CoD.textSize.Big, -30)
		MainLobbyButtonPane.playerCountLabel:setFont(CoD.fonts.Big)
		MainLobbyButtonPane.playerCountLabel:setRGB(CoD.offWhite.r, CoD.offWhite.g, CoD.offWhite.b)
		local PlayerCountText = CoD.Menu.GetOnlinePlayerCountText()
		local PlayerCountUpdateTimer = nil
		if PlayerCountText ~= "" then
			MainLobbyButtonPane.playerCountLabel:setText(PlayerCountText)
			PlayerCountUpdateTimer = LUI.UITimer.new(60000, "update_online_player_count", false, MainLobbyButtonPane.playerCountLabel)
		else
			PlayerCountUpdateTimer = LUI.UITimer.new(1000, "update_online_player_count", false, MainLobbyButtonPane.playerCountLabel)
		end
		MainLobbyButtonPane.playerCountLabel:registerEventHandler("update_online_player_count", CoD.MainLobby.UpdateOnlinePlayerCount)
		MainLobbyButtonPane.playerCountLabel.timer = PlayerCountUpdateTimer
		MainLobbyButtonPane:addElement(PlayerCountUpdateTimer)
	end
end

CoD.MainLobby.UpdateOnlinePlayerCount = function(PlayerCountLabel)
	if CoD.isOnlineGame() then
		local PlayerCountText = CoD.Menu.GetOnlinePlayerCountText()
		if PlayerCountText ~= "" then
			PlayerCountLabel:setText(PlayerCountText)
			PlayerCountLabel.timer.interval = 60000
			PlayerCountLabel.timer:reset()
		end
	end
end

-- ============================================================
-- Remaining standard MainLobby functions
-- ============================================================

CoD.MainLobby.FirstSignedInToLive = function(MainLobbyWidget)
	if MainLobbyWidget ~= nil then
		if CoD.isXBOX then
			MainLobbyWidget.anyControllerAllowed = false
		end
		if MainLobbyWidget.friendsButton == nil then
			MainLobbyWidget:addFriendsButton()
		end
	end
end

CoD.MainLobby.LastSignedOutOfLive = function(MainLobbyWidget)
	if MainLobbyWidget ~= nil and CoD.isXBOX then
		MainLobbyWidget.anyControllerAllowed = true
	end
end

CoD.MainLobby.PlayerSelected = function(MainLobbyWidget, PlayerSelectedEvent)
	if MainLobbyWidget.joinable ~= nil and CoD.canJoinSession(UIExpression.GetPrimaryController(), PlayerSelectedEvent.playerXuid) then
		if MainLobbyWidget.joinButton == nil and not MainLobbyWidget.m_blockJoinButton then
			MainLobbyWidget:addJoinButton()
			MainLobbyWidget:addNATType()
		end
	elseif MainLobbyWidget.joinButton ~= nil then
		MainLobbyWidget.joinButton:close()
		MainLobbyWidget.joinButton = nil
	end
	MainLobbyWidget:dispatchEventToChildren(PlayerSelectedEvent)
end

CoD.MainLobby.PlayerDeselected = function(MainLobbyWidget, PlayerDeselectedEvent)
	if MainLobbyWidget.joinButton ~= nil then
		MainLobbyWidget.joinButton:close()
		MainLobbyWidget.joinButton = nil
	end
	MainLobbyWidget:dispatchEventToChildren(PlayerDeselectedEvent)
end

CoD.MainLobby.CurrentPanelChanged = function(MainLobbyWidget, f27_arg1)
	if CoD.isPC then
		MainLobbyWidget.m_blockJoinButton = f27_arg1.id ~= "PanelManager.lobbyPane"
	end
end

CoD.MainLobby.BusyList_Update = function(f28_arg0, f28_arg1, f28_arg2, f28_arg3, f28_arg4)
	CoD.PlayerList.Update(f28_arg0, Engine.GetBusyFriendsOfAllLocalPlayers(f28_arg0.maxRows - f28_arg2), f28_arg2, f28_arg3, f28_arg4)
end

CoD.MainLobby.Update = function(MainLobbyWidget, ClientInstance)
	if MainLobbyWidget == nil then
		return
	elseif UIExpression.IsDemonwareFetchingDone(ClientInstance.controller) == 1 == true then
		MainLobbyWidget.panelManager:processEvent({
			name = "fetching_done"
		})
	end
	CoD.MainLobby.UpdateButtonPaneButtonVisibilty(MainLobbyWidget.buttonPane)
	CoD.MainLobby.UpdateButtonPromptVisibility(MainLobbyWidget)
	MainLobbyWidget:dispatchEventToChildren(ClientInstance)
end

CoD.MainLobby.ClientLeave = function(MainLobbyWidget, ClientInstance)
	Engine.ExecNow(ClientInstance.controller, "leaveAllParties")
	Engine.PartyHostClearUIState()
	CoD.StartMainLobby(ClientInstance.controller)
	CoD.MainLobby.UpdateButtonPaneButtonVisibilty(MainLobbyWidget.buttonPane)
	CoD.MainLobby.UpdateButtonPromptVisibility()
end

CoD.MainLobby.GoBack = function(MainLobbyWidget, ClientInstance)
	Engine.SessionModeResetModes()
	Engine.Exec(ClientInstance.controller, "xstopprivateparty")
	if CoD.isPS3 then
		Engine.Exec(ClientInstance.controller, "signoutSubUsers")
	end
	MainLobbyWidget:setPreviousMenu("MainMenu")
	CoD.Menu.goBack(MainLobbyWidget, ClientInstance.controller)
end

CoD.MainLobby.Back = function(MainLobbyWidget, ClientInstance)
	if CoD.Lobby.OpenSignOutPopup(MainLobbyWidget, ClientInstance) == true then
		return
	elseif UIExpression.IsPrimaryLocalClient(ClientInstance.controller) == 0 then
		Engine.Exec(ClientInstance.controller, "signclientout")
		MainLobbyWidget:processEvent({
			name = "controller_backed_out"
		})
		return
	elseif UIExpression.AloneInPartyIgnoreSplitscreen(ClientInstance.controller, 1) == 0 then
		local CustomLeaveMessage = {
			params = {}
		}
		if not CoD.isPartyHost() then
			CustomLeaveMessage.titleText = Engine.Localize("MENU_LEAVE_LOBBY_TITLE")
			CustomLeaveMessage.messageText = Engine.Localize("MENU_LEAVE_LOBBY_CLIENT_WARNING")
			table.insert(CustomLeaveMessage.params, {
				leaveHandler = CoD.MainLobby.ClientLeave,
				leaveEvent = "client_leave",
				leaveText = Engine.Localize("MENU_LEAVE_LOBBY_AND_PARTY"),
				debugHelper = "You're a client of a private party, remove you from the party"
			})
		else
			CustomLeaveMessage.titleText = Engine.Localize("MENU_DISBAND_PARTY_TITLE")
			CustomLeaveMessage.messageText = Engine.Localize("MENU_DISBAND_PARTY_HOST_WARNING")
			table.insert(CustomLeaveMessage.params, {
				leaveHandler = CoD.MainLobby.GoBack,
				leaveEvent = "host_leave",
				leaveText = Engine.Localize("MENU_LEAVE_AND_DISBAND_PARTY"),
				debugHelper = "You're the leader of a private party, choosing this will disband your party"
			})
		end
		CoD.Lobby.ConfirmLeave(MainLobbyWidget, ClientInstance.controller, nil, nil, CustomLeaveMessage)
	else
		CoD.MainLobby.GoBack(MainLobbyWidget, ClientInstance)
	end
end

CoD.MainLobby.AddLobbyPaneElements = function(LobbyPane, MenuParty)
	CoD.LobbyPanes.addLobbyPaneElements(LobbyPane, MenuParty, UIExpression.DvarInt(nil, "party_maxlocalplayers_mainlobby"))
	LobbyPane.body.lobbyList.joinableList = CoD.JoinableList.New({
		leftAnchor = true,
		rightAnchor = true,
		left = 0,
		right = 0,
		topAnchor = true,
		bottomAnchor = false,
		top = 0,
		bottom = 0
	}, false, "", "joinableList", LobbyPane.id)
	LobbyPane.body.lobbyList.joinableList.pane = LobbyPane
	LobbyPane.body.lobbyList.joinableList.maxRows = CoD.MaxPlayerListRows - 2
	LobbyPane.body.lobbyList.joinableList.statusText = Engine.Localize("MENU_PLAYERLIST_FRIENDS_PLAYING")
	LobbyPane.body.lobbyList:addElement(LobbyPane.body.lobbyList.joinableList)
end

CoD.MainLobby.ButtonListButtonGainFocus = function(f34_arg0, ClientInstance)
	f34_arg0:dispatchEventToParent({
		name = "add_party_privacy_button"
	})
	CoD.Lobby.ButtonListButtonGainFocus(f34_arg0, ClientInstance)
end

CoD.MainLobby.ButtonListAddButton = function(f35_arg0, f35_arg1, f35_arg2, f35_arg3)
	local f35_local0 = CoD.Lobby.ButtonListAddButton(f35_arg0, f35_arg1, f35_arg2, f35_arg3)
	f35_local0:registerEventHandler("gain_focus", CoD.MainLobby.ButtonListButtonGainFocus)
	return f35_local0
end

CoD.MainLobby.AddButtonPaneElements = function(f36_arg0)
	CoD.LobbyPanes.addButtonPaneElements(f36_arg0)
	f36_arg0.body.buttonList.addButton = CoD.MainLobby.ButtonListAddButton
end

CoD.MainLobby.PopulateButtonPaneElements = function(MainLobbyButtonPane)
	CoD.MainLobby.PopulateButtons(MainLobbyButtonPane)
	CoD.MainLobby.UpdateButtonPaneButtonVisibilty(MainLobbyButtonPane)
end

CoD.MainLobby.GoToFindingGames_Zombie = function(MainLobbyWidget, ClientInstance)
	Engine.Exec(ClientInstance.controller, "xstartparty")
	Engine.Exec(ClientInstance.controller, "updategamerprofile")
	local PublicGameLobbyMenu = MainLobbyWidget:openMenu("PublicGameLobby", ClientInstance.controller)
	PublicGameLobbyMenu:setPreviousMenu("MainLobby")
	PublicGameLobbyMenu:registerAnimationState("hide", {
		alpha = 0
	})
	PublicGameLobbyMenu:animateToState("hide")
	PublicGameLobbyMenu:registerAnimationState("show", {
		alpha = 1
	})
	PublicGameLobbyMenu:animateToState("show", 500)
	MainLobbyWidget:close()
end

CoD.MainLobby.ButtonPromptJoin = function(MainLobbyWidget, ClientInstance)
	if UIExpression.IsGuest(ClientInstance.controller) == 1 then
		local popup = MainLobbyWidget:openPopup("Error", ClientInstance.controller)
		popup:setMessage(Engine.Localize("XBOXLIVE_NOGUESTACCOUNTS"))
		popup.anyControllerAllowed = true
		return
	end
	if MainLobbyWidget.lobbyPane.body.lobbyList.selectedPlayerXuid ~= nil then
		Engine.SetDvar("selectedPlayerXuid", MainLobbyWidget.lobbyPane.body.lobbyList.selectedPlayerXuid)
		CoD.joinPlayer(ClientInstance.controller, MainLobbyWidget.lobbyPane.body.lobbyList.selectedPlayerXuid)
	end
end

-- ============================================================
-- Plutonium-specific handlers
-- ============================================================

CoD.MainLobby.OpenIMGUIServerBrowser = function(MainLobbyWidget, ClientInstance)
	Engine.Exec(ClientInstance.controller, "plutoniumServers")
end

CoD.MainLobby.OpenModsList = function(MainLobbyWidget, ClientInstance)
	MainLobbyWidget:openMenu("Mods", ClientInstance.controller, {
		parent = "MainLobby"
	})
	MainLobbyWidget:close()
end

CoD.MainLobby.OpenSessionRejoinPopup = function(MainLobbyWidget, ClientInstance)
	MainLobbyWidget:openPopup("RejoinSessionPopup", ClientInstance.controller)
end

CoD.MainLobby.elite_registration_ended = function(MainLobbyWidget, ClientInstance)
	if UIExpression.IsGuest(ClientInstance.controller) == 1 then
		MainLobbyWidget:openPopup("popup_guest_contentrestricted", ClientInstance.controller)
		return
	elseif Engine.IsPlayerEliteRegistered(ClientInstance.controller) then
		if Engine.ELaunchAppSearch(ClientInstance.controller) then
			MainLobbyWidget:openPopup("EliteAppLaunchExecPopup", ClientInstance.controller)
		else
			MainLobbyWidget:openPopup("EliteAppDownloadPopup", ClientInstance.controller)
		end
	end
end

CoD.MainLobby.OpenEliteAppPopup = function(MainLobbyWidget, ClientInstance)
	if UIExpression.IsGuest(ClientInstance.controller) == 1 then
		MainLobbyWidget:openPopup("popup_guest_contentrestricted", ClientInstance.controller)
		return
	elseif Engine.IsPlayerEliteRegistered(ClientInstance.controller) then
		if Engine.ELaunchAppSearch(ClientInstance.controller) then
			MainLobbyWidget:openPopup("EliteAppLaunchExecPopup", ClientInstance.controller)
		else
			MainLobbyWidget:openPopup("EliteAppDownloadPopup", ClientInstance.controller)
		end
	else
		MainLobbyWidget:openPopup("EliteRegistrationPopup", ClientInstance.controller)
	end
end

-- ============================================================
-- Main Menu Creation
-- ============================================================

LUI.createMenu.MainLobby = function(LocalClientIndex)
	local MainLobbyName = Engine.Localize(CoD.MPZM("MENU_MULTIPLAYER_CAPS", "MENU_ZOMBIES_CAPS"))
	local MainLobbyWidget = CoD.Lobby.New("MainLobby", LocalClientIndex, nil, MainLobbyName)
	MainLobbyWidget.controller = LocalClientIndex
	MainLobbyWidget.anyControllerAllowed = true
	MainLobbyWidget:setPreviousMenu("MainMenu")
	if CoD.isPC then
		MainLobbyWidget.m_blockJoinButton = true
	end
	if CoD.isZombie == true then
		Engine.Exec(LocalClientIndex, "xsessionupdate")
		MainLobbyWidget:registerEventHandler("open_solo_lobby_zombie", CoD.MainLobby.OpenSoloLobby_Zombie)
		MainLobbyWidget:registerEventHandler("restartMatchmaking", CoD.MainLobby.GoToFindingGames_Zombie)
		Engine.SetDvar("party_readyPercentRequired", 0)
	elseif (CoD.isXBOX or CoD.isPS3) and Engine.IsEliteAvailable() and Engine.IsEliteButtonAvailable() then
		MainLobbyWidget:registerEventHandler("open_eliteapp_popup", CoD.MainLobby.OpenEliteAppPopup)
		MainLobbyWidget:registerEventHandler("elite_registration_ended", CoD.MainLobby.elite_registration_ended)
	end
	MainLobbyWidget:addTitle(MainLobbyName)
	MainLobbyWidget.addButtonPaneElements = CoD.MainLobby.AddButtonPaneElements
	MainLobbyWidget.populateButtonPaneElements = CoD.MainLobby.PopulateButtonPaneElements
	MainLobbyWidget.addLobbyPaneElements = CoD.MainLobby.AddLobbyPaneElements
	MainLobbyWidget:updatePanelFunctions()

	-- Standard event handlers
	MainLobbyWidget:registerEventHandler("partylobby_update", CoD.MainLobby.Update)
	MainLobbyWidget:registerEventHandler("button_prompt_back", CoD.MainLobby.Back)
	MainLobbyWidget:registerEventHandler("first_signed_in", CoD.MainLobby.FirstSignedInToLive)
	MainLobbyWidget:registerEventHandler("last_signed_out", CoD.MainLobby.LastSignedOutOfLive)
	MainLobbyWidget:registerEventHandler("player_selected", CoD.MainLobby.PlayerSelected)
	MainLobbyWidget:registerEventHandler("player_deselected", CoD.MainLobby.PlayerDeselected)
	MainLobbyWidget:registerEventHandler("current_panel_changed", CoD.MainLobby.CurrentPanelChanged)
	MainLobbyWidget:registerEventHandler("open_player_match_party_lobby", CoD.MainLobby.OpenPlayerMatchPartyLobby)
	MainLobbyWidget:registerEventHandler("open_league_play_party_lobby", CoD.MainLobby.OpenLeagueSelectionPopup)
	MainLobbyWidget:registerEventHandler("playlist_selected", CoD.MainLobby.OpenLeaguePlayPartyLobby)
	MainLobbyWidget:registerEventHandler("open_custom_games_lobby", CoD.MainLobby.OpenCustomGamesLobby)
	MainLobbyWidget:registerEventHandler("open_theater_lobby", CoD.MainLobby.OpenTheaterLobby)
	MainLobbyWidget:registerEventHandler("open_cod_tv", CoD.MainLobby.OpenCODTV)
	MainLobbyWidget:registerEventHandler("open_barracks", CoD.MainLobby.OpenBarracks)
	if CoD.isWIIU then
		MainLobbyWidget:registerEventHandler("open_controls_menu", CoD.MainLobby.OpenControlsMenu)
	end
	MainLobbyWidget:registerEventHandler("open_options_menu", CoD.MainLobby.OpenOptionsMenu)
	MainLobbyWidget:registerEventHandler("open_session_rejoin_popup", CoD.MainLobby.OpenSessionRejoinPopup)
	MainLobbyWidget:registerEventHandler("button_prompt_join", CoD.MainLobby.ButtonPromptJoin)
	MainLobbyWidget:registerEventHandler("open_store", CoD.MainLobby.OpenStore)
	MainLobbyWidget:registerEventHandler("open_server_browser_mainlobby", CoD.MainLobby.OpenIMGUIServerBrowser)
	MainLobbyWidget:registerEventHandler("open_mods_menu", CoD.MainLobby.OpenModsList)

	-- DeckOps event handlers
	MainLobbyWidget:registerEventHandler("deckops_open_servers", CoD.DeckOps.OpenServerList)
	MainLobbyWidget:registerEventHandler("deckops_unlock_all", CoD.DeckOps.UnlockAll)
	MainLobbyWidget:registerEventHandler("deckops_reset_stats", CoD.DeckOps.ResetStatsConfirm)

	MainLobbyWidget.lobbyPane.body.lobbyList:setSplitscreenSignInAllowed(true)
	CoD.MainLobby.PopulateButtons(MainLobbyWidget.buttonPane)
	CoD.MainLobby.UpdateButtonPaneButtonVisibilty(MainLobbyWidget.buttonPane)
	CoD.MainLobby.UpdateButtonPromptVisibility(MainLobbyWidget)
	if CoD.useController then
		if CoD.isZombie then
			MainLobbyWidget.buttonPane.body.buttonList:selectElementIndex(1)
		elseif not MainLobbyWidget.buttonPane.body.buttonList:restoreState() then
			if CoD.isPartyHost() then
				-- Default focus to DeckOps Servers button
			end
		end
	end
	MainLobbyWidget.categoryInfo = CoD.Lobby.CreateInfoPane()
	MainLobbyWidget.playlistInfo = CoD.Lobby.CreateInfoPane()
	MainLobbyWidget.lobbyPane.body:close()
	MainLobbyWidget.lobbyPane.body = nil
	CoD.MainLobby.AddLobbyPaneElements(MainLobbyWidget.lobbyPane, Engine.Localize("MENU_PARTY_CAPS"))
	if UIExpression.AnySignedInToLive() == 1 then
		CoD.MainLobby.FirstSignedInToLive(MainLobbyWidget)
	else
		CoD.MainLobby.LastSignedOutOfLive(MainLobbyWidget)
	end
	Engine.SystemNeedsUpdate(nil, "party")
	if CoD.isPS3 then
		MainLobbyWidget.anyControllerAllowed = false
	end
	if not CoD.isZombie then
		CoD.CheckClasses.CheckClasses()
	end
	Engine.SessionModeSetOnlineGame(true)
	return MainLobbyWidget
end
