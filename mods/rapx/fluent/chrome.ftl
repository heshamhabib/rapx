## mainmenu.yaml
label-px-mainmenu-kicker = RED ALERT  //  PROJECT X
label-px-mainmenu-title = Command Center
label-px-version-kicker = PROJECT X  //  VERSION
label-px-version-engine = OPENRA { $engine }
label-px-version-build = OPENRA { $engine }  ·  COMMIT { $build }

## language.yaml
button-px-main-menu-language = Language
button-px-language-apply = Apply
label-px-language-kicker = PROJECT X  //  COMMS PROTOCOL
label-px-language-title = Language
label-px-language-subtitle = Choose the language for menus, orders and briefings.
label-px-language-active = ACTIVE
label-px-language-selected = SELECTED
label-px-language-rtl = RIGHT-TO-LEFT
label-px-language-coverage = INTERFACE
label-px-language-note = Double-click a language or press Apply. The interface reloads in the new language.
label-px-language-pending = Press Apply to switch. The interface reloads in the new language.
label-px-language-name-en = English
label-px-language-name-ar = Arabic
label-px-language-name-de = German
label-px-language-name-fr = French
label-px-language-name-zh = Chinese
label-px-language-name-vi = Vietnamese

## Skirmish lobby title (engine Game.CreateLocalServer)
label-skirmish-game-name = Skirmish Game

## gamesave-loading.yaml
label-gamesave-loading-screen-title = Loading Saved Game
label-gamesave-loading-screen-desc = Press Escape to cancel loading and return to the main menu

## ingame-observer.yaml
button-observer-widgets-pause-tooltip = Pause
button-observer-widgets-play-tooltip = Play

button-observer-widgets-slow =
    .tooltip = Slow speed
    .label = 50%

button-observer-widgets-regular =
    .tooltip = Regular speed
    .label = 100%

button-observer-widgets-fast =
    .tooltip = Fast speed
    .label = 200%

button-observer-widgets-maximum =
    .tooltip = Maximum speed
    .label = MAX

label-basic-stats-player-header = Player
label-basic-stats-cash-header = Cash
label-basic-stats-power-header = Power
label-basic-stats-kills-header = Kills
label-basic-stats-deaths-header = Deaths
label-basic-stats-assets-destroyed-header = Destroyed
label-basic-stats-assets-lost-header = Lost
label-basic-stats-experience-header = Score
label-basic-stats-actions-min-header = APM
label-economy-stats-player-header = Player
label-economy-stats-cash-header = Cash
label-economy-stats-income-header = Income
label-economy-stats-assets-header = Assets
label-economy-stats-earned-header = Earned
label-economy-stats-spent-header = Spent
label-economy-stats-harvesters-header = Harvesters
label-economy-stats-derricks-header = Oil Derricks
label-production-stats-player-header = Player
label-production-stats-header = Production
label-support-powers-player-header = Player
label-support-powers-header = Support Powers
label-army-player-header = Player
label-army-header = Army
label-combat-stats-player-header = Player
label-combat-stats-assets-destroyed-header = Destroyed
label-combat-stats-assets-lost-header = Lost
label-combat-stats-units-killed-header = U. Killed
label-combat-stats-units-dead-header = U. Lost
label-combat-stats-buildings-killed-header = B. Killed
label-combat-stats-buildings-dead-header = B. Lost
label-combat-stats-army-value-header = Army Value
label-combat-stats-vision-header = Vision

## ingame-observer.yaml, ingame-player.yaml
label-mute-indicator = Audio Muted
button-top-buttons-options-tooltip = Options
button-top-buttons-home-tooltip = Home: centre on your Construction Yard

## ingame-player.yaml
supportpowers-support-powers-palette =
    .ready = READY
    .hold = ON HOLD

label-support-timer-own = YOURS
label-support-timer-ally = ALLY
label-support-timer-hostile = HOSTILE
label-support-timer-ready = READY
label-support-timer-hold = ON HOLD

button-command-bar-attack-move =
    .tooltip = Attack Move
    .tooltipdesc =
    Selected units will move to the desired location
    and attack any enemies they encounter en route.

    Hold <(Ctrl)> while targeting to order an Assault Move
    that attacks any units or structures encountered en route.

    Left-click icon then right-click on target location.

button-command-bar-force-move =
    .tooltip = Force Move
    .tooltipdesc =
    Selected units will move to the desired location
     - Default activity for the target is suppressed
     - Vehicles will attempt to crush enemies at the target location
     - Helicopters will land at the target location
     - Chrono Tanks will teleport towards the target location

    Left-click icon then right-click on target.
    Hold <(Alt)> to activate temporarily while commanding units.

button-command-bar-force-attack =
    .tooltip = Force Attack
    .tooltipdesc =
    Selected units will attack the targeted unit or location
     - Default activity for the target is suppressed
     - Allows targeting of own or ally forces
     - Long-range artillery units will always target the
       location, ignoring units and buildings

    Left-click icon then right-click on target.
    Hold <(Ctrl)> to activate temporarily while commanding units.

button-command-bar-guard =
    .tooltip = Guard
    .tooltipdesc =
    Selected units will follow the targeted unit.

    Left-click icon then right-click on target unit.

button-command-bar-deploy =
    .tooltip = Deploy
    .tooltipdesc =
    Selected units will perform their default deploy activity
     - MCVs will unpack into a Construction Yard
     - Construction Yards will re-pack into a MCV
     - Transports will unload their passengers
     - Demolition Trucks and MAD Tanks will self-destruct
     - Minelayers will deploy a mine
     - Aircraft will return to base

    Acts immediately on selected units.

button-command-bar-scatter =
    .tooltip = Scatter
    .tooltipdesc =
    Selected units will stop their current activity
    and move to a nearby location.

    Acts immediately on selected units.

button-command-bar-stop =
    .tooltip = Stop
    .tooltipdesc =
    Selected units will stop their current activity.
    Selected buildings will reset their rally point.

    Acts immediately on selected targets.

button-command-bar-queue-orders =
    .tooltip = Waypoint Mode
    .tooltipdesc =
    Use Waypoint Mode to give multiple linking commands
    to the selected units. Units will execute the commands
    immediately upon receiving them.

    Left-click icon then give commands in the game world.
    Hold <(Shift)> to activate temporarily while commanding units.

button-stance-bar-attackanything =
    .tooltip = Attack Anything Stance
    .tooltipdesc =
    Set the selected units to Attack Anything stance:
     - Units will attack enemy units and structures on sight
     - Units will pursue attackers across the battlefield

button-stance-bar-defend =
    .tooltip = Defend Stance
    .tooltipdesc =
    Set the selected units to Defend stance:
     - Units will attack enemy units on sight
     - Units will not move or pursue enemies

button-stance-bar-returnfire =
    .tooltip = Return Fire Stance
    .tooltipdesc =
    Set the selected units to Return Fire stance:
     - Units will retaliate against enemies that attack them
     - Units will not move or pursue enemies

button-stance-bar-holdfire =
    .tooltip = Hold Fire Stance
    .tooltipdesc =
    Set the selected units to Hold Fire stance:
     - Units will not fire upon enemies
     - Units will not move or pursue enemies

button-top-buttons-beacon-tooltip = Place Beacon
button-top-buttons-sell-tooltip = Sell
button-top-buttons-power-tooltip = Power Down
button-top-buttons-repair-tooltip = Repair

productionpalette-sidebar-production-palette =
    .ready = READY
    .hold = ON HOLD

button-production-types-building-tooltip = Buildings
button-production-types-defense-tooltip = Defense
button-production-types-infantry-tooltip = Infantry
button-production-types-vehicle-tooltip = Vehicles
button-production-types-aircraft-tooltip = Aircraft
button-production-types-naval-tooltip = Naval
button-production-types-scroll-up-tooltip = Scroll up
button-production-types-scroll-down-tooltip = Scroll down


## ingame-player.yaml (RAPX sidebar)
label-px-sidebar-repair = REPAIR
label-px-sidebar-sell = SELL
label-px-sidebar-power = POWER
label-px-sidebar-beacon = BEACON
label-px-sidebar-radar = RADAR
label-px-sidebar-credits = CREDITS
label-px-sidebar-time = MISSION TIME
label-px-sidebar-no-radar = NO RADAR SIGNAL
label-px-sidebar-build-radar = Build a Radar Dome to activate
label-px-panel-commands = COMMANDS
label-px-panel-actions = STRUCTURE ACTIONS
label-px-panel-rally = RALLY
button-px-panel-rally-tooltip = Set Rally Point

## lobby.yaml, lobby-players.yaml, lobby-options.yaml (RAPX lobby)
label-px-lobby-subtitle = OPERATION LOBBY
label-px-lobby-chip-players = PLAYERS
label-px-lobby-chip-speed = SPEED
label-px-lobby-chip-cash = CASH
label-px-lobby-summary = MATCH SUMMARY
label-px-lobby-sum-cash = Starting cash
label-px-lobby-sum-units = Starting units
label-px-lobby-sum-speed = Game speed
label-px-lobby-sum-time = Time limit
label-px-lobby-sum-treaty = Peace treaty
label-px-lobby-col-commander = COMMANDER
label-px-lobby-col-color = COLOR
label-px-lobby-col-nation = NATION
label-px-lobby-col-team = TEAM
label-px-lobby-col-handicap = HANDICAP
label-px-lobby-col-titan = TITAN
checkbox-px-lobby-ready-tooltip = Ready / not ready: click when you are ready to start
dropdownbutton-lobby-players-titan-tooltip = A giant that fights for this player from the start. If it dies it cannot be rebuilt.
label-px-lobby-col-spawn = SPAWN
label-px-lobby-col-status = STATUS
label-px-lobby-open-slot = WAITING FOR COMMANDER
label-px-lobby-section-battlefield = BATTLEFIELD
label-px-lobby-section-rules = RULES
label-px-lobby-section-setup = MATCH SETUP
label-px-music-soundtrack = SOUNDTRACK
label-px-lobby-section-developer = DEVELOPER
label-px-color-title = TEAM COLOR

## ingame-info.yaml, ingame-infostats.yaml
label-px-info-subtitle = BATTLE REPORT
label-px-info-mission = MISSION STATUS
label-px-info-rank = RANK
label-px-info-commander = NATION  ·  COMMANDER
label-px-info-status = STATUS

## ingame-menu.yaml (PxExitToDesktopLogic)
menu-ingame-px-exit-desktop = Exit to Desktop

dialog-px-exit-desktop =
    .title = Exit to Desktop
    .prompt = Quit the game? Unsaved progress will be lost.
    .confirm = Exit
    .cancel = Stay
menu-ingame-px-controls = Controls

## Control schemes (IDEA-11): settings-input.yaml, mainmenu-prompts.yaml
label-px-control-scheme = Control Scheme:
label-px-mouse-style = Mouse Style:

options-px-control-scheme =
    .ra2 = Red Alert 2
    .ra2-right = Red Alert 2 (right-click orders)
    .openra = OpenRA default
    .custom = Custom

label-px-control-scheme-desc =
    .ra2 = Left click selects and gives orders, right click deselects, right drag scrolls. RA2 keys (T, G, D, Z…).
    .ra2-right = Right click gives orders, right drag scrolls. RA2 keys (T, G, D, Z…).
    .openra = The standard OpenRA mouse and keys.
    .custom = Your own mix of settings. Pick a scheme to reset everything.

notification-px-waypoint-mode = Waypoint mode: click to add points, double-click or press the key again to send.

## ingame-controls.yaml (PxControlsHelpLogic)
label-px-controls-title = Controls
label-px-controls-scheme = Control scheme: { $scheme }
button-px-controls-close = Close
label-px-controls-unbound = (not set)

label-px-controls-header =
    .mouse = MOUSE
    .units = UNIT COMMANDS
    .base = BASE
    .sidebar = SIDEBAR TABS
    .teams = TEAMS & VIEW

label-px-controls-mouse-select = Select units
    .input = Left click / left drag
label-px-controls-mouse-order = Move / attack
    .classic = Left click
    .modern = Right click
label-px-controls-mouse-deselect = Deselect
    .classic = Right click
    .modern = Left click on empty ground
label-px-controls-mouse-scroll = Scroll the map
    .right = Hold right button + drag
    .middle = Hold middle button + drag
label-px-controls-mouse-same-type = Select that type on screen
    .input = Double-click a unit
label-px-controls-mouse-primary = Make a factory primary
    .input = Double-click the factory
label-px-controls-mouse-add = Add to selection
    .input = Shift + click
label-px-controls-mouse-force-fire = Force fire
    .input = Ctrl + click
label-px-controls-mouse-force-move = Force move
    .input = Alt + click

label-px-controls-note =
    .twice = (twice: whole map)
    .waypoint = (again: send route)

label-px-controls-team =
    .create = Create team
    .select = Select team (twice: centre view)
    .add = Add team to selection
    .jump = Centre view on team

label-px-controls-bookmark =
    .save = Save map position
    .jump = Jump to map position

## PxTreatyManager (IDEA-10)
options-peace-treaty =
    .no-treaty = No treaty
    .options =
        { $minutes ->
            [one] { $minutes } minute
           *[other] { $minutes } minutes
        }

notification-peace-treaty-started =
    A peace treaty is in effect for { $minutes ->
        [one] { $minutes } minute
       *[other] { $minutes } minutes
    }. No attacks until it ends. Type /endtreaty to vote to end it early.
notification-peace-treaty-minutes-left =
    Peace treaty ends in { $minutes ->
        [one] { $minutes } minute
       *[other] { $minutes } minutes
    }.
notification-peace-treaty-seconds-left = Peace treaty ends in { $seconds }...
notification-peace-treaty-ended = The peace treaty has ended. War!
notification-peace-treaty-blocked = Treaty in effect: you cannot attack other players yet.
notification-peace-treaty-voted = { $player } votes to end the treaty early ({ $votes }/{ $needed }).
notification-peace-treaty-vote-passed = All players agreed: the treaty ends in { $seconds } seconds.
notification-peace-treaty-not-active = There is no peace treaty in effect.
description-end-treaty = vote to end the peace treaty early
label-peace-treaty-header = CEASEFIRE IN EFFECT
label-peace-treaty-header-final = CEASEFIRE EXPIRING
label-peace-treaty-war = WAR
label-peace-treaty-war-sub = ALL UNITS ENGAGE
label-peace-treaty-votes = END-TREATY VOTES { $votes }/{ $needed }
label-peace-treaty-hint = TYPE /ENDTREATY TO VOTE FOR WAR

## Enemy remaining counter (top right of the battlefield)
label-px-enemy-remaining-structures = ENEMY STRUCTURES
label-px-enemy-remaining-forces = ENEMY FORCES
label-px-enemy-remaining-detail-structures = { $buildings } BUILDINGS · { $mobile } MCV
label-px-enemy-remaining-detail-forces = { $buildings } BUILDINGS · { $mobile } UNITS

## PxCategoryBar (IDEA-05)
label-px-category-all = All
label-px-category-other = Other

## PxWeatherManager (IDEA-20)
options-weather =
    .off = Off
    .visual = Visual only

options-weather-changes =
    .rare = Rare
    .normal = Normal
    .frequent = Frequent

notification-weather-forecast = Weather forecast: { $weather } in { $seconds } seconds.
notification-weather-arrived = Weather: { $weather }.

label-weather =
    .clear = Clear skies
    .rain = Rain
    .thunderstorm = Thunderstorm
    .snow = Snow
    .blizzard = Blizzard
    .fog = Fog
    .sandstorm = Sandstorm
    .strongwind = Strong wind
    .heathaze = Heat haze

## PxWeatherBadge (IDEA-20)
label-px-weather-title = WEATHER
label-px-weather-changing = CHANGING
label-px-weather-forecast = FORECAST
label-px-weather-stable = STABLE
label-px-weather-next-short = NEXT
label-px-weather-incoming-short = INCOMING
label-px-weather-tooltip-now = Now: { $weather }
label-px-weather-tooltip-next = Next: { $weather } in { $time }
label-px-weather-tooltip-fixed = The weather on this map does not change.
label-px-weather-tooltip-mode = Visual only: weather does not affect units.

## Display settings: graphics quality
checkbox-px-hd-world =
    .label = HD World Detail
    .tooltip = Render the battlefield at the screen's full resolution so HD units and buildings stay sharp when zoomed in. Much heavier on the GPU on high-resolution (Retina) screens.

checkbox-px-smooth-motion =
    .label = Smooth Unit Motion
    .tooltip = Draw moving units between game ticks so they glide at the full frame rate instead of stepping 25 times a second.

checkbox-px-ground-effects =
    .label = Ground Effects
    .tooltip = Terrain detail textures and moving cloud shadows. Costs the same every frame whatever is happening, so it is the first thing to turn off on a laptop's built-in graphics. Applies to the next match.

checkbox-px-weather-effects =
    .label = Weather Effects
    .tooltip = Rain, snow, fog, sandstorms and the light each weather casts, and the pressure waves of big explosions bending the picture. The weather still changes and is still announced, it is just not drawn. Applies to the next match.

dropdown-px-weather-detail =
    .label = Weather Detail:
    .tooltip = How much detail the weather is drawn with. A storm is the most expensive thing on screen, so turning this down buys frames back without losing the weather. Low keeps every weather recognisable but drops the splash crowns under rain, the furthest rain and snow layers and the branches on lightning. Applies at once.
    .high = High
    .medium = Medium
    .low = Low

## Display settings: graphics card
dropdown-px-gpu-preference =
    .label = Graphics Card:
    .tooltip = Which graphics card Windows runs the game on. Most gaming laptops have two: a power-saving one built into the processor and a fast dedicated one. This is the same choice as Windows Settings > System > Display > Graphics, and it applies when the game next starts.
    .high = High performance
    .saving = Power saving
    .windows = Let Windows decide
label-px-gpu-in-use = Graphics card in use: { $name }
label-px-gpu-unknown = not reported by the graphics driver
label-px-gpu-direct3d = Direct3D { $version } through ANGLE
label-px-gpu-opengl = OpenGL { $version }
label-px-gpu-driver = { $api }, driver { $version }
label-px-gpu-others = { $api }. Also in this PC: { $names }
label-px-gpu-all = { $api }. Graphics cards in this PC: { $names }
label-px-gpu-hint-integrated = The game is on the power-saving graphics. Choose High performance above and restart the game for a much higher frame rate.
label-px-gpu-hint-software = No graphics driver is in use, so the processor is drawing the game. Install the latest driver for your graphics card.
label-px-gpu-hint-no-driver = A graphics card in this PC is missing its driver. Install it from the NVIDIA, AMD or Intel website.
label-px-gpu-hint-restart = Restart the game to switch graphics card.

## Observer sidebar
label-px-observer-title = OBSERVER
label-px-observer-live = LIVE
label-px-observer-alive = IN BATTLE
label-px-observer-view = CAMERA VIEW
label-px-observer-players = PLAYERS
