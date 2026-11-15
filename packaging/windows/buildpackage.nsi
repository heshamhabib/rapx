; Copyright (c) The OpenRA Developers and Contributors
; This file is part of OpenRA.
;
;  OpenRA is free software: you can redistribute it and/or modify
;  it under the terms of the GNU General Public License as published by
;  the Free Software Foundation, either version 3 of the License, or
;  (at your option) any later version.
;
;  OpenRA is distributed in the hope that it will be useful,
;  but WITHOUT ANY WARRANTY; without even the implied warranty of
;  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;  GNU General Public License for more details.
;
;  You should have received a copy of the GNU General Public License
;  along with OpenRA.  If not, see <https://www.gnu.org/licenses/>.


!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "WordFunc.nsh"
!include "WinMessages.nsh"
!include "LogicLib.nsh"

;***************************
;Interface theme
;
;The bitmaps referenced here are generated at build time from the mod's own menu
;key art by packaging/windows/generate-theme.sh, so the wizard matches the game
;chrome rather than shipping the stock grey NSIS look. The colours come from
;mod.config.
;***************************
!define MUI_ICON "${SRCDIR}\${MOD_ID}.ico"
!define MUI_UNICON "${SRCDIR}\${MOD_ID}.ico"

;MUI2 defines .onGUIInit itself, so the outer-window repaint hooks in here instead.
!define MUI_CUSTOMFUNCTION_GUIINIT DarkenWindow
!define MUI_CUSTOMFUNCTION_UNGUIINIT un.DarkenWindow

!define MUI_BGCOLOR "${THEME_BGCOLOR}"
!define MUI_TEXTCOLOR "${THEME_TEXTCOLOR}"

!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "${THEME_DIR}\header.bmp"
!define MUI_HEADERIMAGE_BITMAP_STRETCH "FitControl"
!define MUI_HEADERIMAGE_UNBITMAP "${THEME_DIR}\header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP_STRETCH "FitControl"

;Rendered at 3x so they stay sharp when NSIS scales them up on HiDPI displays.
!define MUI_WELCOMEFINISHPAGE_BITMAP "${THEME_DIR}\welcome.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP_STRETCH "FitControl"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${THEME_DIR}\welcome.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP_STRETCH "FitControl"

;SetCtlColors cannot recolour the label of a themed checkbox (NSIS bug #443), so the
;"run now" tick on the finish page would be drawn in the system text colour -- black
;on black here. MUI only works around that in high contrast mode unless this is set,
;and it affects nothing outside the finish page.
!define MUI_FORCECLASSICCONTROLS

!define MUI_FINISHPAGE_LINK_COLOR "${THEME_ACCENTCOLOR}"

;Dark install log. The progress bar on that page is recoloured in InstFilesPageShow,
;because a visually styled bar ignores the colours set here.
!define MUI_INSTFILESPAGE_COLORS "${THEME_TEXTCOLOR} ${THEME_BGCOLOR}"
!define MUI_INSTFILESPAGE_PROGRESSBAR "smooth"

!define MUI_WELCOMEPAGE_TITLE "${PACKAGING_DISPLAY_NAME}"
!define MUI_WELCOMEPAGE_TEXT "Setup will install ${PACKAGING_DISPLAY_NAME} ${TAG} on your computer.$\r$\n$\r$\nClose any running copy of the game before continuing.$\r$\n$\r$\nClick Next to continue."

Name "${PACKAGING_DISPLAY_NAME}"
OutFile "${OUTFILE}"

ManifestDPIAware true

Unicode True

Function .onInit
	!ifndef USE_PROGRAMFILES32
		SetRegView 64
	!endif
	ReadRegStr $INSTDIR HKLM "Software\${PACKAGING_WINDOWS_REGISTRY_KEY}" "InstallDir"
	StrCmp $INSTDIR "" unset done
	unset:
	!ifndef USE_PROGRAMFILES32
		StrCpy $INSTDIR "$PROGRAMFILES64\${PACKAGING_WINDOWS_INSTALL_DIR_NAME}"
	!else
		StrCpy $INSTDIR "$PROGRAMFILES32\${PACKAGING_WINDOWS_INSTALL_DIR_NAME}"
	!endif
	done:
FunctionEnd

SetCompressor lzma
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!define MUI_PAGE_CUSTOMFUNCTION_SHOW DarkenPage
!insertmacro MUI_PAGE_LICENSE "${PACKAGING_WINDOWS_LICENSE_FILE}"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW DarkenPage
!insertmacro MUI_PAGE_DIRECTORY

!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKLM"
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\${PACKAGING_WINDOWS_REGISTRY_KEY}"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "OpenRA"

Var StartMenuFolder
!define MUI_PAGE_CUSTOMFUNCTION_SHOW DarkenPage
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

!define MUI_PAGE_CUSTOMFUNCTION_SHOW DarkenPage
!insertmacro MUI_PAGE_COMPONENTS
!define MUI_PAGE_CUSTOMFUNCTION_SHOW InstFilesPageShow
!insertmacro MUI_PAGE_INSTFILES

;A finish page so setup ends the way a game installer is expected to, with the
;option to play straight away.
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PACKAGING_DISPLAY_NAME}"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchGame
!define MUI_FINISHPAGE_LINK "Visit the ${PACKAGING_DISPLAY_NAME} website"
!define MUI_FINISHPAGE_LINK_LOCATION "${PACKAGING_WEBSITE_URL}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

;***************************
;Interface callbacks
;***************************
Function DarkenWindow

	;The page dialogs sit inside an outer window that keeps the system colours, which
	;would frame every darkened page in a light border. Paint the outer window and its
	;branding strip to match.
	SetCtlColors $HWNDPARENT "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"
	GetDlgItem $R0 $HWNDPARENT 1256
	SetCtlColors $R0 "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"

FunctionEnd

Function un.DarkenWindow

	SetCtlColors $HWNDPARENT "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"
	GetDlgItem $R0 $HWNDPARENT 1256
	SetCtlColors $R0 "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"

FunctionEnd

Function DarkenPage

	;MUI_BGCOLOR only reaches the header strip and the welcome/finish pages; the
	;interior pages are ordinary Win32 dialogs that would stay system-light next to a
	;black header. Repaint the page dialog and every control on it. The Back/Next/Cancel
	;buttons live on the outer window and are deliberately left native, so they still
	;look and behave like standard Windows buttons.
	FindWindow $R0 "#32770" "" $HWNDPARENT
	SetCtlColors $R0 "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"

	StrCpy $R1 1000
	${Do}
		GetDlgItem $R2 $R0 $R1
		${If} $R2 <> 0
			;Group box captions and check marks are painted by the visual styles engine in
			;the system text colour, which is invisible against a dark page. Dropping the
			;theme on the control falls back to the classic renderer, which honours the
			;colours set below. Buttons on the outer window keep their theme.
			System::Call 'uxtheme::SetWindowTheme(p $R2, w " ", w " ")'
			SetCtlColors $R2 "${THEME_TEXTCOLOR}" "${THEME_BGCOLOR}"
		${EndIf}
		IntOp $R1 $R1 + 1
	${LoopUntil} $R1 > 1100

FunctionEnd

Function InstFilesPageShow

	;Same treatment as the other pages: InstallColors only reaches the log control, so
	;the status text and the area around the progress bar would stay system-light.
	Call DarkenPage

	;A themed progress bar is drawn by the visual styles engine, which ignores
	;PBM_SETBARCOLOR. Drop the theme on that one control first, then paint it in the
	;mod's accent colour so the install page matches the rest of the wizard.
	System::Call 'uxtheme::SetWindowTheme(p $mui.InstFilesPage.ProgressBar, w " ", w " ")'
	SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBARCOLOR} 0 ${THEME_ACCENT_BGR}
	SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBKCOLOR} 0 ${THEME_BG_BGR}

FunctionEnd

Function LaunchGame

	;Setup runs elevated, and a game started directly from here would inherit that --
	;writing its settings and logs into the administrator profile instead of the
	;player's. Going via explorer.exe hands the launch back to the logged-in user.
	Exec '"$WINDIR\explorer.exe" "$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe"'

FunctionEnd

;***************************
;Section Definitions
;***************************
Section "-Reg" Reg

	; Installation directory
	WriteRegStr HKLM "Software\${PACKAGING_WINDOWS_REGISTRY_KEY}" "InstallDir" $INSTDIR

	; Join server URL Scheme
	WriteRegStr HKLM "Software\Classes\openra-${MOD_ID}-${TAG}" "" "URL:Join OpenRA server"
	WriteRegStr HKLM "Software\Classes\openra-${MOD_ID}-${TAG}" "URL Protocol" ""
	WriteRegStr HKLM "Software\Classes\openra-${MOD_ID}-${TAG}\DefaultIcon" "" "$INSTDIR\${MOD_ID}.ico,0"
	WriteRegStr HKLM "Software\Classes\openra-${MOD_ID}-${TAG}\Shell\Open\Command" "" "$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe Launch.URI=%1"

	!ifdef USE_DISCORDID
		WriteRegStr HKLM "Software\Classes\discord-${USE_DISCORDID}" "" "URL:Run game ${USE_DISCORDID} protocol"
		WriteRegStr HKLM "Software\Classes\discord-${USE_DISCORDID}" "URL Protocol" ""
		WriteRegStr HKLM "Software\Classes\discord-${USE_DISCORDID}\DefaultIcon" "" "$INSTDIR\${MOD_ID}.ico,0"
		WriteRegStr HKLM "Software\Classes\discord-${USE_DISCORDID}\Shell\Open\Command" "" "$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe"
	!endif

SectionEnd

Section "Game" GAME
	SectionIn RO

	SetOutPath "$INSTDIR"
	File "${SRCDIR}\*.exe"
	File "${SRCDIR}\*.dll.config"
	File "${SRCDIR}\*.dll"
	File "${SRCDIR}\*.ico"
	File "${SRCDIR}\*.deps.json"
	File "${SRCDIR}\*.runtimeconfig.json"
	File "${SRCDIR}\global mix database.dat"
	File "${SRCDIR}\IP2LOCATION-LITE-DB1.IPV6.BIN.ZIP"
	File "${SRCDIR}\VERSION"
	File "${SRCDIR}\AUTHORS"
	File "${SRCDIR}\COPYING"
	File /r "${SRCDIR}\mods"

	!insertmacro MUI_STARTMENU_WRITE_BEGIN Application
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\${PACKAGING_DISPLAY_NAME}.lnk" "$OUTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" "" \
			"$OUTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" "" "" "" ""
	!insertmacro MUI_STARTMENU_WRITE_END

	SetOutPath "$INSTDIR\glsl"
	File "${SRCDIR}\glsl\*.frag"
	File "${SRCDIR}\glsl\*.vert"

	; Estimated install size for the control panel properties
	${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
	IntFmt $0 "0x%08X" $0
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "EstimatedSize" "$0"

	SetShellVarContext all
	CreateDirectory "$APPDATA\OpenRA\ModMetadata"
	SetOutPath "$INSTDIR"
	nsExec::ExecToLog '"$INSTDIR\OpenRA.Utility.exe" ${MOD_ID} --register-mod "$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" system'
	nsExec::ExecToLog '"$INSTDIR\OpenRA.Utility.exe" ${MOD_ID} --clear-invalid-mod-registrations system'
	SetShellVarContext current

SectionEnd

Section "Desktop Shortcut" DESKTOPSHORTCUT
	SetOutPath "$INSTDIR"
	CreateShortCut "$DESKTOP\OpenRA - ${PACKAGING_DISPLAY_NAME}.lnk" "$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" "" \
		"$INSTDIR\${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" "" "" "" ""
SectionEnd

;***************************
;Uninstaller Sections
;***************************
Section "-Uninstaller"
	WriteUninstaller $INSTDIR\uninstaller.exe
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "DisplayName" "${PACKAGING_DISPLAY_NAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "UninstallString" "$INSTDIR\uninstaller.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "InstallLocation" "$INSTDIR"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "DisplayIcon" "$INSTDIR\${MOD_ID}.ico"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "Publisher" "${PACKAGING_AUTHORS}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "URLInfoAbout" "${PACKAGING_WEBSITE_URL}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "DisplayVersion" "${TAG}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "NoModify" "1"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}" "NoRepair" "1"
SectionEnd

!macro Clean UN
Function ${UN}Clean
	nsExec::ExecToLog '"$INSTDIR\OpenRA.Utility.exe" ${MOD_ID} --unregister-mod system'

	RMDir /r $INSTDIR\mods
	RMDir /r $INSTDIR\maps
	RMDir /r $INSTDIR\glsl
	Delete $INSTDIR\*.exe
	Delete $INSTDIR\*.dll
	Delete $INSTDIR\*.ico
	Delete $INSTDIR\*.dll.config
	Delete $INSTDIR\*.deps.json
	Delete $INSTDIR\*.runtimeconfig.json
	Delete $INSTDIR\VERSION
	Delete $INSTDIR\AUTHORS
	Delete $INSTDIR\COPYING
	Delete "$INSTDIR\global mix database.dat"
	Delete $INSTDIR\IP2LOCATION-LITE-DB1.IPV6.BIN.ZIP

	RMDir /r $INSTDIR\Support

	!ifndef USE_PROGRAMFILES32
		SetRegView 64
	!endif

	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PACKAGING_WINDOWS_REGISTRY_KEY}"
	DeleteRegKey HKLM "Software\Classes\openra-${MOD_ID}-${TAG}"

	!ifdef USE_DISCORDID
		DeleteRegKey HKLM "Software\Classes\discord-${USE_DISCORDID}"
	!endif

	Delete $INSTDIR\uninstaller.exe
	RMDir $INSTDIR

	!insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

	; Clean up start menu: Delete all our icons, and the OpenRA folder
	; *only* if we were the only installed version
	Delete "$SMPROGRAMS\$StartMenuFolder\${PACKAGING_DISPLAY_NAME}.lnk"
	RMDir "$SMPROGRAMS\$StartMenuFolder"

	Delete "$DESKTOP\OpenRA - ${PACKAGING_DISPLAY_NAME}.lnk"
	DeleteRegKey HKLM "Software\${PACKAGING_WINDOWS_REGISTRY_KEY}"
FunctionEnd
!macroend

!insertmacro Clean ""
!insertmacro Clean "un."

Section "Uninstall"
	Call un.Clean
SectionEnd

;***************************
;Section Descriptions
;***************************
LangString DESC_GAME ${LANG_ENGLISH} "${PACKAGING_DISPLAY_NAME} game files."
LangString DESC_DESKTOPSHORTCUT ${LANG_ENGLISH} "Place shortcut on the Desktop."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
	!insertmacro MUI_DESCRIPTION_TEXT ${GAME} $(DESC_GAME)
	!insertmacro MUI_DESCRIPTION_TEXT ${DESKTOPSHORTCUT} $(DESC_DESKTOPSHORTCUT)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;***************************
;Callbacks
;***************************

Function .onInstFailed
	Call Clean
FunctionEnd
