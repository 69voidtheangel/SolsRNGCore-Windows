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

; SolsRNGCore-Windows input bridge
; AutoHotkey 1.1-compatible. The Python side writes one .cmd file per action.

try
{
    ; DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    DllCall("SetThreadDpiAwarenessContext", "Ptr", -4, "Ptr")
}

ENV_LOCALAPPDATA := A_LocalAppData
if (!ENV_LOCALAPPDATA)
    EnvGet, ENV_LOCALAPPDATA, LOCALAPPDATA

QUEUE_DIR := ENV_LOCALAPPDATA . "\\SolsRNGCore-Windows\\ahk_queue"
STATE_FILE := QUEUE_DIR . "\\state.txt"
RUNNING := true

if !FileExist(QUEUE_DIR)
    FileCreateDir, %QUEUE_DIR%

WriteState("AHK RUN=1")
SetTimer, PollQueue, 40
return

F6::ToggleRun()
F7::SetRun(false)
F8::EmergencyStop()

ToggleRun()
{
    global RUNNING
    RUNNING := !RUNNING
    WriteState("AHK RUN=" . (RUNNING ? "1" : "0"))
}

SetRun(value)
{
    global RUNNING
    RUNNING := value ? true : false
    WriteState("AHK RUN=" . (RUNNING ? "1" : "0"))
}

EmergencyStop()
{
    global RUNNING, QUEUE_DIR
    RUNNING := false
    Loop, Files, % QUEUE_DIR . "\\*.cmd", F
    {
        FileDelete, % A_LoopFileFullPath
    }
    WriteState("AHK EMERGENCY STOP")
}

WriteState(value)
{
    global STATE_FILE
    FileDelete, %STATE_FILE%
    FileAppend, % value . "`n", %STATE_FILE%
}

PollQueue:
{
    global QUEUE_DIR
    if !FileExist(QUEUE_DIR)
        FileCreateDir, %QUEUE_DIR%

    Loop, Files, % QUEUE_DIR . "\\*.cmd", F
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
}
return

ExecuteCommand(command)
{
    global RUNNING

    parts := StrSplit(command, "|")
    if (parts.MaxIndex() < 1)
        return

    op := parts[1]

    if (op = "RUN")
    {
        value := (parts.MaxIndex() >= 2) ? parts[2] : "0"
        SetRun(value = "1" || value = "true")
        return
    }

    if (!RUNNING)
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
