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
APP_DIR := A_LocalAppData . "\SolsRNGCore-Windows"
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
