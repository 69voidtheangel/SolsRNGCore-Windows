; SolsRNGCore-Windows — AutoHotkey 1.1 bridge
#NoEnv
#SingleInstance Force
#Persistent
#InstallKeybdHook
#InstallMouseHook
SendMode, Input
SetWorkingDir, %A_ScriptDir%
SetBatchLines, -1
SetKeyDelay, -1, -1
SetMouseDelay, -1
SetDefaultMouseSpeed, 0
SetTitleMatchMode, 2

; The GUI writes this INI. Everything below intentionally uses AHK 1.1 syntax.
EnvGet, ENV_LOCALAPPDATA, LOCALAPPDATA
APP_DIR := ENV_LOCALAPPDATA . "\SolsRNGCore-Windows"
QUEUE_DIR := APP_DIR . "\ahk_queue"
STATE_FILE := QUEUE_DIR . "\state.txt"
SETTINGS_FILE := APP_DIR . "\ahk_settings.ini"
RUNNING := true
ENABLED := true
REQUIRE_ROBLOX := true
POLL_MS := 40
SEND_MODE := "Input"
KEY_DELAY := -1
PRESS_DURATION := -1
MOUSE_DELAY := -1
MOUSE_SPEED := 0
ROBLOX_TITLE := "Roblox"
TOGGLE_HOTKEY := "F6"
STOP_HOTKEY := "F7"
EMERGENCY_HOTKEY := "F8"
CLEAR_QUEUE_ON_EMERGENCY := true
OLD_TOGGLE := ""
OLD_STOP := ""
OLD_EMERGENCY := ""

if !FileExist(APP_DIR)
    FileCreateDir, %APP_DIR%
if !FileExist(QUEUE_DIR)
    FileCreateDir, %QUEUE_DIR%
LoadSettings()
BuildGui()
WriteState("AHK RUN=" . (RUNNING ? "1" : "0"))
return

LoadSettings()
{
    global SETTINGS_FILE, ENABLED, REQUIRE_ROBLOX, POLL_MS, SEND_MODE
    global KEY_DELAY, PRESS_DURATION, MOUSE_DELAY, MOUSE_SPEED, ROBLOX_TITLE
    global TOGGLE_HOTKEY, STOP_HOTKEY, EMERGENCY_HOTKEY, CLEAR_QUEUE_ON_EMERGENCY
    global OLD_TOGGLE, OLD_STOP, OLD_EMERGENCY
    IniRead, v, %SETTINGS_FILE%, General, Enabled, 1
    ENABLED := (v = "1")
    IniRead, v, %SETTINGS_FILE%, General, RequireRobloxForeground, 1
    REQUIRE_ROBLOX := (v = "1")
    IniRead, v, %SETTINGS_FILE%, General, PollMs, 40
    POLL_MS := v + 0
    if (POLL_MS < 10)
        POLL_MS := 10
    if (POLL_MS > 1000)
        POLL_MS := 1000
    IniRead, v, %SETTINGS_FILE%, General, SendMode, Input
    if (v != "Input" && v != "Event" && v != "Play")
        v := "Input"
    SEND_MODE := v
    SendMode, %SEND_MODE%
    IniRead, v, %SETTINGS_FILE%, General, KeyDelayMs, -1
    KEY_DELAY := v + 0
    IniRead, v, %SETTINGS_FILE%, General, PressDurationMs, -1
    PRESS_DURATION := v + 0
    IniRead, v, %SETTINGS_FILE%, General, MouseDelayMs, -1
    MOUSE_DELAY := v + 0
    IniRead, v, %SETTINGS_FILE%, General, DefaultMouseSpeed, 0
    MOUSE_SPEED := v + 0
    SetKeyDelay, %KEY_DELAY%, %PRESS_DURATION%
    SetMouseDelay, %MOUSE_DELAY%
    SetDefaultMouseSpeed, %MOUSE_SPEED%
    IniRead, v, %SETTINGS_FILE%, General, RobloxWindowTitle, Roblox
    ROBLOX_TITLE := v
    IniRead, v, %SETTINGS_FILE%, General, ToggleHotkey, F6
    TOGGLE_HOTKEY := v
    IniRead, v, %SETTINGS_FILE%, General, StopHotkey, F7
    STOP_HOTKEY := v
    IniRead, v, %SETTINGS_FILE%, General, EmergencyHotkey, F8
    EMERGENCY_HOTKEY := v
    IniRead, v, %SETTINGS_FILE%, General, ClearQueueOnEmergency, 1
    CLEAR_QUEUE_ON_EMERGENCY := (v = "1")
    if (OLD_TOGGLE != "")
        Hotkey, %OLD_TOGGLE%, Off
    if (OLD_STOP != "")
        Hotkey, %OLD_STOP%, Off
    if (OLD_EMERGENCY != "")
        Hotkey, %OLD_EMERGENCY%, Off
    Hotkey, %TOGGLE_HOTKEY%, HandleToggle, On
    Hotkey, %STOP_HOTKEY%, HandleStop, On
    Hotkey, %EMERGENCY_HOTKEY%, HandleEmergency, On
    OLD_TOGGLE := TOGGLE_HOTKEY
    OLD_STOP := STOP_HOTKEY
    OLD_EMERGENCY := EMERGENCY_HOTKEY
    SetTimer, PollQueue, Off
    SetTimer, PollQueue, %POLL_MS%
    UpdateGuiFromSettings()
}

HandleToggle:
    RUNNING := !RUNNING
    WriteState("AHK RUN=" . (RUNNING ? "1" : "0"))
return

HandleStop:
    RUNNING := false
    WriteState("AHK RUN=0")
return

HandleEmergency:
    EmergencyStop()
return


BuildGui()
{
    global AHK_GUI_HWND, ENABLED, REQUIRE_ROBLOX, POLL_MS, SEND_MODE
    global KEY_DELAY, PRESS_DURATION, MOUSE_DELAY, MOUSE_SPEED, ROBLOX_TITLE
    global TOGGLE_HOTKEY, STOP_HOTKEY, EMERGENCY_HOTKEY, CLEAR_QUEUE_ON_EMERGENCY, RUNNING
    Gui, New, +HwndAHK_GUI_HWND +MinSize, SolsRNGCore-Windows AHK 1.1
    Gui, Margin, 12, 12
    Gui, Font, s10, Segoe UI
    Gui, Add, Text, xm w500, SolsRNGCore-Windows - AutoHotkey 1.1 Control Panel
    Gui, Add, Text, xm y+4, Direct AHK control panel. Settings are shared with the Python macro.
    Gui, Add, GroupBox, xm y+12 w500 h82, Runtime
    Gui, Add, CheckBox, xp+12 yp+22 vGuiEnabled, Enable AHK bridge
    GuiControl,, GuiEnabled, %ENABLED%
    Gui, Add, CheckBox, xp+0 y+10 vGuiRequireRoblox, Only send input while Roblox is foreground
    GuiControl,, GuiRequireRoblox, %REQUIRE_ROBLOX%
    Gui, Add, GroupBox, xm y+12 w500 h182, Input
    Gui, Add, Text, xp+12 yp+22, Poll (ms)
    Gui, Add, Edit, x+8 yp-3 w70 vGuiPollMs, %POLL_MS%
    Gui, Add, Text, x+18 yp+3, Send mode
    Gui, Add, DropDownList, x+8 yp-3 w90 vGuiSendMode, Input||Event|Play
    GuiControl, ChooseString, GuiSendMode, %SEND_MODE%
    Gui, Add, Text, xm+24 y+14, Key delay
    Gui, Add, Edit, x+8 yp-3 w70 vGuiKeyDelay, %KEY_DELAY%
    Gui, Add, Text, x+18 yp+3, Press duration
    Gui, Add, Edit, x+8 yp-3 w70 vGuiPressDuration, %PRESS_DURATION%
    Gui, Add, Text, xm+24 y+14, Mouse delay
    Gui, Add, Edit, x+8 yp-3 w70 vGuiMouseDelay, %MOUSE_DELAY%
    Gui, Add, Text, x+18 yp+3, Mouse speed
    Gui, Add, Edit, x+8 yp-3 w70 vGuiMouseSpeed, %MOUSE_SPEED%
    Gui, Add, Text, xm+24 y+14, Roblox title
    Gui, Add, Edit, x+8 yp-3 w285 vGuiRobloxTitle, %ROBLOX_TITLE%
    Gui, Add, GroupBox, xm y+12 w500 h112, Hotkeys
    Gui, Add, Text, xp+12 yp+22, Toggle
    Gui, Add, Edit, x+8 yp-3 w70 vGuiToggleHotkey, %TOGGLE_HOTKEY%
    Gui, Add, Text, x+18 yp+3, Stop
    Gui, Add, Edit, x+8 yp-3 w70 vGuiStopHotkey, %STOP_HOTKEY%
    Gui, Add, Text, x+18 yp+3, Emergency
    Gui, Add, Edit, x+8 yp-3 w70 vGuiEmergencyHotkey, %EMERGENCY_HOTKEY%
    Gui, Add, CheckBox, xm+24 y+14 vGuiClearQueue, Clear queued commands on emergency stop
    GuiControl,, GuiClearQueue, %CLEAR_QUEUE_ON_EMERGENCY%
    Gui, Add, Button, xm w110 gSaveAndReload, Apply / Reload
    Gui, Add, Button, x+8 w90 gStartFromGui, Start
    Gui, Add, Button, x+8 w90 gStopFromGui, Stop
    Gui, Add, Button, x+8 w90 gEmergencyFromGui, Emergency
    Gui, Add, Button, x+8 w90 gTestFromGui, Test
    Gui, Add, Text, xm y+12 w500 vGuiStatus, Status:
    UpdateGuiStatus()
    Menu, Tray, NoStandard
    Menu, Tray, Add, Show Control Panel, ShowGui
    Menu, Tray, Add, Start, StartFromGui
    Menu, Tray, Add, Stop, StopFromGui
    Menu, Tray, Add, Emergency Stop, EmergencyFromGui
    Menu, Tray, Add, Reload Settings, SaveAndReload
    Menu, Tray, Add
    Menu, Tray, Add, Exit, ExitScript
    Menu, Tray, Default, Show Control Panel
    Gui, Show, AutoSize Center
}

UpdateGuiStatus(message := "")
{
    global AHK_GUI_HWND, RUNNING, ENABLED
    if (AHK_GUI_HWND = "")
        return
    status := (message != "") ? "Status: " . message : "Status: " . (RUNNING ? "RUNNING" : "STOPPED") . " | AHK " . (ENABLED ? "enabled" : "disabled")
    GuiControl,, GuiStatus, %status%
}

UpdateGuiFromSettings()
{
    global AHK_GUI_HWND, ENABLED, REQUIRE_ROBLOX, POLL_MS, SEND_MODE, KEY_DELAY, PRESS_DURATION
    global MOUSE_DELAY, MOUSE_SPEED, ROBLOX_TITLE, TOGGLE_HOTKEY, STOP_HOTKEY, EMERGENCY_HOTKEY, CLEAR_QUEUE_ON_EMERGENCY
    if (AHK_GUI_HWND = "")
        return
    GuiControl,, GuiEnabled, %ENABLED%
    GuiControl,, GuiRequireRoblox, %REQUIRE_ROBLOX%
    GuiControl,, GuiPollMs, %POLL_MS%
    GuiControl, ChooseString, GuiSendMode, %SEND_MODE%
    GuiControl,, GuiKeyDelay, %KEY_DELAY%
    GuiControl,, GuiPressDuration, %PRESS_DURATION%
    GuiControl,, GuiMouseDelay, %MOUSE_DELAY%
    GuiControl,, GuiMouseSpeed, %MOUSE_SPEED%
    GuiControl,, GuiRobloxTitle, %ROBLOX_TITLE%
    GuiControl,, GuiToggleHotkey, %TOGGLE_HOTKEY%
    GuiControl,, GuiStopHotkey, %STOP_HOTKEY%
    GuiControl,, GuiEmergencyHotkey, %EMERGENCY_HOTKEY%
    GuiControl,, GuiClearQueue, %CLEAR_QUEUE_ON_EMERGENCY%
    UpdateGuiStatus()
}

SaveGuiSettings()
{
    global SETTINGS_FILE, GuiEnabled, GuiRequireRoblox, GuiPollMs, GuiSendMode, GuiKeyDelay, GuiPressDuration
    global GuiMouseDelay, GuiMouseSpeed, GuiRobloxTitle, GuiToggleHotkey, GuiStopHotkey, GuiEmergencyHotkey, GuiClearQueue
    Gui, Submit, NoHide
    poll := GuiPollMs + 0
    if (poll < 10)
        poll := 10
    if (poll > 1000)
        poll := 1000
    mode := GuiSendMode
    if (mode != "Input" && mode != "Event" && mode != "Play")
        mode := "Input"
    IniWrite, % (GuiEnabled ? 1 : 0), %SETTINGS_FILE%, General, Enabled
    IniWrite, % (GuiRequireRoblox ? 1 : 0), %SETTINGS_FILE%, General, RequireRobloxForeground
    IniWrite, %poll%, %SETTINGS_FILE%, General, PollMs
    IniWrite, %mode%, %SETTINGS_FILE%, General, SendMode
    IniWrite, % (GuiKeyDelay + 0), %SETTINGS_FILE%, General, KeyDelayMs
    IniWrite, % (GuiPressDuration + 0), %SETTINGS_FILE%, General, PressDurationMs
    IniWrite, % (GuiMouseDelay + 0), %SETTINGS_FILE%, General, MouseDelayMs
    IniWrite, % (GuiMouseSpeed + 0), %SETTINGS_FILE%, General, DefaultMouseSpeed
    IniWrite, %GuiRobloxTitle%, %SETTINGS_FILE%, General, RobloxWindowTitle
    IniWrite, %GuiToggleHotkey%, %SETTINGS_FILE%, General, ToggleHotkey
    IniWrite, %GuiStopHotkey%, %SETTINGS_FILE%, General, StopHotkey
    IniWrite, %GuiEmergencyHotkey%, %SETTINGS_FILE%, General, EmergencyHotkey
    IniWrite, % (GuiClearQueue ? 1 : 0), %SETTINGS_FILE%, General, ClearQueueOnEmergency
}

SaveAndReload:
    SaveGuiSettings()
    LoadSettings()
    WriteState("AHK SETTINGS RELOADED")
    UpdateGuiStatus("settings reloaded")
return

StartFromGui:
    RUNNING := true
    WriteState("AHK RUN=1")
    UpdateGuiStatus("RUNNING")
return

StopFromGui:
    RUNNING := false
    WriteState("AHK RUN=0")
    UpdateGuiStatus("STOPPED")
return

EmergencyFromGui:
    EmergencyStop()
    UpdateGuiStatus("EMERGENCY STOP")
return

TestFromGui:
    WriteState("AHK PONG " . A_TickCount)
    UpdateGuiStatus("bridge test sent")
return

ShowGui:
    Gui, Show
return

GuiClose:
GuiEscape:
    Gui, Hide
return

ExitScript:
    ExitApp
return

EmergencyStop()
{
    global RUNNING, QUEUE_DIR, CLEAR_QUEUE_ON_EMERGENCY
    RUNNING := false
    if (CLEAR_QUEUE_ON_EMERGENCY)
    {
        Loop, Files, % QUEUE_DIR . "\*.cmd", F
        {
            FileDelete, % A_LoopFileFullPath
        }
    }
    WriteState("AHK EMERGENCY STOP")
}

IsInputAllowed()
{
    global ENABLED, RUNNING, REQUIRE_ROBLOX, ROBLOX_TITLE
    if (!ENABLED || !RUNNING)
        return false
    if (!REQUIRE_ROBLOX || ROBLOX_TITLE = "")
        return true
    return WinActive(ROBLOX_TITLE) != 0
}

WriteState(value)
{
    global STATE_FILE
    FileDelete, %STATE_FILE%
    FileAppend, % value . Chr(10), %STATE_FILE%
}

PollQueue:
    if !FileExist(QUEUE_DIR)
        FileCreateDir, %QUEUE_DIR%
    Loop, Files, % QUEUE_DIR . "\*.cmd", F
    {
        path := A_LoopFileFullPath
        command := ""
        FileRead, command, %path%
        if (ErrorLevel)
            continue
        FileDelete, %path%
        command := Trim(command, " `t`r`n")
        if (command != "")
            ExecuteCommand(command)
    }
return

ExecuteCommand(command)
{
    parts := StrSplit(command, "|")
    if (parts.MaxIndex() < 1)
        return
    op := parts[1]
    if (op = "RUN")
    {
        value := (parts.MaxIndex() >= 2) ? parts[2] : "0"
        RUNNING := (value = "1" || value = "true")
        WriteState("AHK RUN=" . (RUNNING ? "1" : "0"))
        return
    }
    if (op = "RELOAD_SETTINGS")
    {
        LoadSettings()
        WriteState("AHK SETTINGS RELOADED")
        return
    }
    if (op = "EMERGENCY_STOP")
    {
        EmergencyStop()
        return
    }
    if (op = "PING")
    {
        WriteState("AHK PONG " . A_TickCount)
        return
    }
    if (!IsInputAllowed())
        return
    if (op = "PRESS" && parts.MaxIndex() >= 2)
    {
        key := parts[2]
        Send, {%key%}
        return
    }
    if (op = "KEYDOWN" && parts.MaxIndex() >= 2)
    {
        key := parts[2]
        Send, {%key% down}
        return
    }
    if (op = "KEYUP" && parts.MaxIndex() >= 2)
    {
        key := parts[2]
        Send, {%key% up}
        return
    }
    if (op = "CLICK" && parts.MaxIndex() >= 4)
    {
        x := parts[2] + 0
        y := parts[3] + 0
        count := parts[4] + 0
        if (count < 1)
            count := 1
        Click, %x%, %y%, %count%, Left
        return
    }
    if (op = "MOVE" && parts.MaxIndex() >= 3)
    {
        x := parts[2] + 0
        y := parts[3] + 0
        MouseMove, %x%, %y%, 0
        return
    }
    if (op = "TYPE" && parts.MaxIndex() >= 2)
    {
        text := parts[2]
        Send, {Text}%text%
        return
    }
    if (op = "SLEEP" && parts.MaxIndex() >= 2)
    {
        ms := parts[2] + 0
        if (ms > 0)
            Sleep, %ms%
        return
    }
}

