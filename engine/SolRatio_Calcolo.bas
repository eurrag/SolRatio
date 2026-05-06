Attribute VB_Name = "SolRatio_Calcolo"
'
' SolRatio
' Versione letta automaticamente da engine\VERSION (fallback hardcoded)
' Architettura: un file SolRatio_progetto.xlsm per ogni progetto
' Script Python in ..\..\engine\calcola_br.py
'

Private Function GetVersion() As String
' Legge la versione da engine\VERSION (single source of truth).
' Fallback: versione hardcoded se il file non e' raggiungibile.
    Dim engineDir As String
    Dim vPath As String
    Dim fNum As Integer
    Dim ver As String

    engineDir = GetEngineDir()
    If engineDir <> "" Then
        vPath = engineDir & "VERSION"
        On Error Resume Next
        If Dir(vPath) <> "" Then
            fNum = FreeFile
            Open vPath For Input As #fNum
            Line Input #fNum, ver
            Close #fNum
            ver = Trim(ver)
            If ver <> "" Then
                GetVersion = ver
                Exit Function
            End If
        End If
        On Error GoTo 0
    End If

    ' Fallback hardcoded (aggiornare solo se VERSION non disponibile)
    GetVersion = "4.0.0"
End Function

Private Function GetProjDir() As String
' Restituisce il percorso locale della cartella progetto.
' Gestisce file su OneDrive/SharePoint convertendo URL -> percorso locale.
    Dim p As String
    Dim oneDriveBase As String
    Dim urlPath As String
    Dim localPath As String
    Dim pos As Long
    
    ' 1) Tentativo diretto: ThisWorkbook.Path locale
    p = ThisWorkbook.Path
    If p <> "" And Left(LCase(p), 4) <> "http" Then
        If Right(p, 1) <> "\" Then p = p & "\"
        GetProjDir = p
        Exit Function
    End If
    
    ' 2) OneDrive: converte URL in percorso locale
    '    URL tipico: https://d.docs.live.net/XXXXXXXX/Documenti/A1 Studio/...
    '    Locale:     C:\Users\Utente\OneDrive\Documenti\A1 Studio/...
    '
    '    Strategia: prende Environ("OneDrive") come base locale,
    '    dall'URL rimuove la parte https://dominio/CID/ e appende il resto.
    
    urlPath = ThisWorkbook.FullName
    If Left(LCase(urlPath), 4) <> "http" Then
        ' Non e' un URL, ma non ha backslash - file non salvato?
        GetProjDir = ""
        Exit Function
    End If
    
    ' Normalizza slash
    urlPath = Replace(urlPath, "/", "\")
    
    ' Decodifica caratteri URL-encoded comuni (v3.1)
    urlPath = Replace(urlPath, "%20", " ")
    urlPath = Replace(urlPath, "%23", "#")
    urlPath = Replace(urlPath, "%28", "(")
    urlPath = Replace(urlPath, "%29", ")")
    urlPath = Replace(urlPath, "%5B", "[")
    urlPath = Replace(urlPath, "%5D", "]")
    
    ' Trova la base OneDrive locale
    oneDriveBase = Environ("OneDriveConsumer")
    If oneDriveBase = "" Then oneDriveBase = Environ("OneDrive")
    If oneDriveBase = "" Then oneDriveBase = Environ("OneDriveCommercial")
    
    If oneDriveBase = "" Then
        GetProjDir = ""
        Exit Function
    End If
    
    ' Dall'URL, salta dominio e CID:
    ' https:\d.docs.live.net\XXXXXXXX\Documenti\...
    ' Dopo "live.net\" c'e' il CID, dopo il CID c'e' il percorso relativo
    
    ' Cerca "live.net\" o "sharepoint.com\"
    Dim markers As Variant
    markers = Array("live.net\", "sharepoint.com\", "1drv.ms\")
    Dim found As Boolean
    found = False
    
    Dim marker As Variant
    For Each marker In markers
        pos = InStr(1, LCase(urlPath), LCase(CStr(marker)))
        If pos > 0 Then
            ' Salta il marker
            urlPath = Mid(urlPath, pos + Len(CStr(marker)))
            ' Salta il CID (primo segmento)
            pos = InStr(urlPath, "\")
            If pos > 0 Then
                urlPath = Mid(urlPath, pos) ' include il backslash iniziale
            End If
            found = True
            Exit For
        End If
    Next marker
    
    If Not found Then
        ' Prova approccio generico: cerca dopo il 4° backslash
        ' https:\host\path\CID\resto...
        Dim cnt As Long
        cnt = 0
        For pos = 1 To Len(urlPath)
            If Mid(urlPath, pos, 1) = "\" Then
                cnt = cnt + 1
                If cnt = 4 Then
                    urlPath = Mid(urlPath, pos)
                    found = True
                    Exit For
                End If
            End If
        Next pos
    End If
    
    If Not found Then
        GetProjDir = ""
        Exit Function
    End If
    
    ' Costruisci percorso locale: OneDrive base + percorso relativo
    localPath = oneDriveBase & urlPath
    
    ' Estrai cartella dal percorso completo del file
    pos = InStrRev(localPath, "\")
    If pos > 0 Then
        localPath = Left(localPath, pos)
    End If
    
    ' Verifica che la cartella esista
    On Error Resume Next
    Dim testDir As String
    testDir = Dir(localPath & "nul")
    ' Verifica alternativa con Dir su cartella
    If Dir(localPath, vbDirectory) <> "" Or Err.Number = 0 Then
        GetProjDir = localPath
    Else
        GetProjDir = ""
    End If
    On Error GoTo 0

End Function

Private Function GetEngineDir() As String
' Cerca la cartella engine\ risalendo da GetProjDir() fino a 5 livelli.
' Verifica la presenza di calcola_br.py per conferma.
    Dim d As String
    Dim pos As Long
    Dim i As Integer
    
    d = GetProjDir()
    If d = "" Then GetEngineDir = "": Exit Function
    
    For i = 1 To 5
        If Right(d, 1) = "\" Then d = Left(d, Len(d) - 1)
        pos = InStrRev(d, "\")
        If pos = 0 Then GetEngineDir = "": Exit Function
        d = Left(d, pos)
        ' Verifica che engine\ esista e contenga lo script
        On Error Resume Next
        If Dir(d & "engine\calcola_br.py") <> "" Then
            On Error GoTo 0
            GetEngineDir = d & "engine\"
            Exit Function
        End If
        On Error GoTo 0
    Next i
    GetEngineDir = ""
End Function

Private Function GetInputPath() As String
' Percorso completo del file di input (questo file)
    Dim d As String
    d = GetProjDir()
    If d = "" Then GetInputPath = "": Exit Function
    GetInputPath = d & ThisWorkbook.Name
End Function

Private Function GetPythonExe() As String
    Dim p As String
    On Error Resume Next
    p = Trim(CStr(ThisWorkbook.Sheets("Launcher").Range("B3").Value))
    On Error GoTo 0
    If p = "" Or p = "0" Then
        ' B3 vuota: cerca Python automaticamente
        p = DetectPython()
        If p <> "" Then
            ' Salva in B3 per le prossime volte
            On Error Resume Next
            ThisWorkbook.Sheets("Launcher").Range("B3").Value = p
            On Error GoTo 0
        Else
            p = "python"
        End If
    End If
    GetPythonExe = p
End Function

Private Function DetectPython() As String
' Cerca Python sul sistema. Scarta lo stub Microsoft Store (WindowsApps).
' v3.2.1: aggiunto py.exe launcher come primo tentativo.
' Cerca in ordine: py.exe launcher, where python, percorsi noti.
    Dim tmpFile As String
    Dim fNum As Integer
    Dim ln As String
    Dim bestPath As String
    
    ' Metodo 0: Python Launcher for Windows (py.exe)
    ' Installato di default con Python.org e gestisce versioni multiple.
    Dim pyLauncher As String
    pyLauncher = Environ("SYSTEMROOT") & "\py.exe"
    If pyLauncher <> "\py.exe" And Dir(pyLauncher) <> "" Then
        DetectPython = pyLauncher
        Exit Function
    End If
    
    ' Metodo 1: esegui "where python" e leggi l'output
    tmpFile = Environ("TEMP") & "\sr_python_detect.txt"
    On Error Resume Next
    Kill tmpFile
    On Error GoTo 0
    
    Shell "cmd /c where python > """ & tmpFile & """ 2>&1", 0
    
    ' Attendi che il file venga scritto (max 3 secondi)
    Dim t As Single: t = Timer
    Do While Timer - t < 3
        DoEvents
        If Dir(tmpFile) <> "" Then
            ' Verifica che non sia vuoto
            If FileLen(tmpFile) > 0 Then Exit Do
        End If
    Loop
    
    ' Piccola pausa extra per completamento scrittura
    Application.Wait Now + TimeSerial(0, 0, 1)
    
    bestPath = ""
    If Dir(tmpFile) <> "" Then
        fNum = FreeFile
        Open tmpFile For Input As #fNum
        Do While Not EOF(fNum)
            Line Input #fNum, ln
            ln = Trim(ln)
            If LCase(ln) Like "*.exe" Then
                ' Scarta lo stub Microsoft Store
                If InStr(LCase(ln), "windowsapps") = 0 Then
                    ' Verifica che il file esista davvero
                    If Dir(ln) <> "" Then
                        bestPath = ln
                        Exit Do  ' Prendi il primo valido
                    End If
                End If
            End If
        Loop
        Close #fNum
        Kill tmpFile
    End If
    
    ' Metodo 2: percorsi noti se where non ha funzionato
    If bestPath = "" Then
        Dim knownPaths As Variant
        knownPaths = Array( _
            Environ("LOCALAPPDATA") & "\Python\bin\python.exe", _
            Environ("LOCALAPPDATA") & "\Programs\Python\Python312\python.exe", _
            Environ("LOCALAPPDATA") & "\Programs\Python\Python311\python.exe", _
            Environ("LOCALAPPDATA") & "\Programs\Python\Python310\python.exe", _
            "C:\ProgramData\anaconda3\python.exe", _
            Environ("USERPROFILE") & "\anaconda3\python.exe", _
            Environ("USERPROFILE") & "\miniconda3\python.exe", _
            "C:\Python312\python.exe", _
            "C:\Python311\python.exe", _
            "C:\Python310\python.exe" _
        )
        Dim kp As Variant
        For Each kp In knownPaths
            If CStr(kp) <> "" And Dir(CStr(kp)) <> "" Then
                bestPath = CStr(kp)
                Exit For
            End If
        Next kp
    End If
    
    DetectPython = bestPath
End Function

Sub RicalcolaBR()
    Dim projDir As String, scriptPath As String, inputPath As String
    Dim logPath As String, batPath As String, sentPath As String
    Dim pythonExe As String, fBat As Integer
    
    projDir = GetProjDir()
    If projDir = "" Then
        MsgBox "Impossibile determinare il percorso locale." & vbCrLf & vbCrLf & _
               "Path: " & ThisWorkbook.Path & vbCrLf & _
               "FullName: " & ThisWorkbook.FullName & vbCrLf & _
               "OneDrive: " & Environ("OneDrive") & vbCrLf & _
               "OneDriveConsumer: " & Environ("OneDriveConsumer") & vbCrLf & vbCrLf & _
               "Soluzioni:" & vbCrLf & _
               "1. Verifica che OneDrive sia sincronizzato" & vbCrLf & _
               "2. Oppure salva una copia locale del file", _
               vbCritical, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    scriptPath = GetEngineDir() & "calcola_br.py"
    inputPath = GetInputPath()
    logPath = projDir & "br_log.txt"
    batPath = projDir & "_br_calc_run.bat"
    sentPath = projDir & ".br_done"
    
    If Dir(scriptPath) = "" Then
        MsgBox "Script non trovato:" & vbCrLf & scriptPath & vbCrLf & vbCrLf & _
               "Cartella progetto: " & projDir & vbCrLf & _
               "Engine cercata: " & GetEngineDir(), _
               vbCritical, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    ' Verifica che il file di input esista localmente (v3.1)
    If Dir(inputPath) = "" Then
        MsgBox "File di input non trovato:" & vbCrLf & inputPath & vbCrLf & vbCrLf & _
               "Il file potrebbe non essere sincronizzato localmente.", _
               vbCritical, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    On Error Resume Next
    Kill sentPath: Kill logPath: Kill batPath
    On Error GoTo 0

    pythonExe = GetPythonExe()
    
    fBat = FreeFile
    Open batPath For Output As #fBat
    Print #fBat, "@echo off"
    Print #fBat, Chr(34) & pythonExe & Chr(34) & " " & _
                 Chr(34) & scriptPath & Chr(34) & " " & _
                 Chr(34) & inputPath & Chr(34) & " > " & _
                 Chr(34) & logPath & Chr(34) & " 2>&1"
    Close #fBat
    
    Shell "cmd /c " & Chr(34) & batPath & Chr(34), 1
    
    MsgBox "Calcolo avviato." & vbCrLf & vbCrLf & _
           "Progetto: " & projDir & vbCrLf & _
           "Input: " & inputPath & vbCrLf & vbCrLf & _
           "Monitora br_log.txt." & vbCrLf & _
           "Quando cmd si chiude, premi 'Verifica calcolo'.", _
           vbInformation, "SolRatio v" & GetVersion()
End Sub

Sub VerificaCalcolo()
    Dim projDir As String, sentPath As String, risPath As String
    Dim logPath As String, logMsg As String, logLine As String, fNum As Integer
    Dim projName As String
    Dim warnMsg As String, wsP As Worksheet
    Dim yrStart As Variant, yrEnd As Variant
    Dim vHmin As Variant, vTau As Variant, vNext As Variant

    projDir = GetProjDir()
    If projDir = "" Then
        MsgBox "Percorso non determinabile.", vbExclamation, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    sentPath = projDir & ".br_done"
    ' Il file di output è denominato risultati_<NomeProgetto>.xlsx
    ' (vedi calcola_br.py: out_path = f'risultati_{proj_name}.xlsx')
    projName = Mid(projDir, InStrRev(projDir, "\", Len(projDir) - 1) + 1)
    If Right(projName, 1) = "\" Then projName = Left(projName, Len(projName) - 1)
    risPath = projDir & "risultati_" & projName & ".xlsx"
    logPath = projDir & "br_log.txt"

    If Dir(sentPath) = "" Then
        ' Fallback: se il sentinel non esiste ma il file risultati si',
        ' il calcolo e completato (sentinel non creato per permessi)
        If Dir(risPath) <> "" Then
            ' Risultati presenti — probabilmente sentinel bloccato da OneDrive
            MsgBox "Completato (sentinella non trovata, ma risultati presenti)." & vbCrLf & vbCrLf & "Possibile blocco OneDrive/antivirus sulla sentinella." & vbCrLf & "I risultati sono stati generati correttamente.", vbInformation, "SolRatio v" & GetVersion()
            GoTo OpenResults
        End If
        logMsg = ""
        fNum = FreeFile
        On Error Resume Next
        Open logPath For Input As #fNum
        Do While Not EOF(fNum)
            Line Input #fNum, logLine
            logMsg = logMsg & logLine & vbCrLf
        Loop
        Close #fNum
        On Error GoTo 0
        If Len(logMsg) > 2000 Then logMsg = "..." & vbCrLf & Right(logMsg, 2000)
        If Trim(logMsg) = "" Then logMsg = "(log non trovato)"
        MsgBox "Non completato." & vbCrLf & vbCrLf & logMsg, vbExclamation, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    On Error Resume Next
    Kill sentPath: Kill projDir & "_br_calc_run.bat"
    On Error GoTo 0
    
OpenResults:
    If Dir(risPath) <> "" Then
        ' --- Warning parametri inusuali ---
        warnMsg = ""
        Set wsP = ThisWorkbook.Sheets("Parametri")
        yrStart = wsP.Range("B41").Value
        yrEnd = wsP.Range("B42").Value
        If IsNumeric(yrStart) And CLng(yrStart) < 2005 Then
            warnMsg = warnMsg & "- Anno inizio " & yrStart & ": PVGIS-SARAH3 disponibile dal 2005." & vbCrLf
        End If
        If IsNumeric(yrEnd) And CLng(yrEnd) > Year(Date) - 2 Then
            warnMsg = warnMsg & "- Anno fine " & yrEnd & ": i dati PVGIS-SARAH3 hanno ~2 anni di ritardo. Ultimo probabile: " & Year(Date) - 2 & "." & vbCrLf
        End If
        vHmin = wsP.Range("B17").Value
        If IsNumeric(vHmin) And CDbl(vHmin) = 0 Then
            warnMsg = warnMsg & "- H_min_terra = 0: pannello tocca il suolo a max inclinazione." & vbCrLf
        End If
        vTau = wsP.Range("B23").Value
        If IsNumeric(vTau) And CDbl(vTau) > 0.5 Then
            warnMsg = warnMsg & "- Trasmittanza " & Format(vTau, "0.00") & ": valore elevato (PV opaco standard: 0)." & vbCrLf
        End If
        vNext = wsP.Range("B44").Value
        If IsNumeric(vNext) And CLng(vNext) = 0 Then
            warnMsg = warnMsg & "- N_ext = 0: pitch isolato, non rappresentativo di impianto esteso." & vbCrLf
        End If

        Workbooks.Open risPath
        If warnMsg <> "" Then
            MsgBox "Completato con parametri inusuali:" & vbCrLf & vbCrLf & warnMsg & vbCrLf & "Verifica i risultati con attenzione.", vbExclamation, "SolRatio v" & GetVersion()
        Else
            MsgBox "Completato! Risultati aperti.", vbInformation, "SolRatio v" & GetVersion()
        End If
    Else
        MsgBox "Sentinella OK ma risultati.xlsx mancante.", vbExclamation, "SolRatio v" & GetVersion()
    End If
End Sub

Sub AggiungiPulsanti()
    Dim ws As Worksheet, btn As Shape, wasProtected As Boolean
    
    If ThisWorkbook.ReadOnly Then
        MsgBox "File in sola lettura.", vbExclamation, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets("Launcher")
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets(1)
        ws.Name = "Launcher"
    End If
    
    ws.Activate: DoEvents
    wasProtected = ws.ProtectContents
    If wasProtected Then ws.Unprotect
    
    ' Aggiorna titolo foglio con versione corrente
    ws.Range("A1").Value = "SOLRATIO AGRIVOLTAICO - Launcher v" & GetVersion()
    
    On Error Resume Next
    ws.Shapes("BtnCalcola").Delete
    ws.Shapes("BtnVerifica").Delete
    ws.Shapes("BtnTest").Delete
    ws.Shapes("BtnSensitivita").Delete
    On Error GoTo 0
    
    ws.EnableSelection = xlNoRestrictions
    On Error GoTo ErrBtn
    
    Set btn = ws.Shapes.AddShape(5, ws.Range("B5").Left, ws.Range("B5").Top, _
              ws.Range("B5:D6").Width, ws.Range("B5:D6").Height)
    FormatButton btn, "BtnCalcola", "RicalcolaBR", "Ricalcola"
    
    Set btn = ws.Shapes.AddShape(5, ws.Range("B8").Left, ws.Range("B8").Top, _
              ws.Range("B8:D9").Width, ws.Range("B8:D9").Height)
    FormatButton btn, "BtnVerifica", "VerificaCalcolo", "Verifica calcolo"
    
    Set btn = ws.Shapes.AddShape(5, ws.Range("B11").Left, ws.Range("B11").Top, _
              ws.Range("B11:C11").Width, ws.Range("B11").Height)
    FormatButton btn, "BtnTest", "TestPython", "Test Python"
    
    Set btn = ws.Shapes.AddShape(5, ws.Range("B13").Left, ws.Range("B13").Top, _
              ws.Range("B13:D14").Width, ws.Range("B13:D14").Height)
    FormatButton btn, "BtnSensitivita", "LanciaSensitivita", "Analisi Sensitivita"
    
    If wasProtected Then ws.Protect
    
    MsgBox "Pulsanti aggiunti." & vbCrLf & vbCrLf & _
           "Progetto: " & GetProjDir() & vbCrLf & _
           "Engine: " & GetEngineDir(), _
           vbInformation, "SolRatio v" & GetVersion()
    Exit Sub

ErrBtn:
    If wasProtected Then ws.Protect
    MsgBox "Errore: " & Err.Number & " - " & Err.Description, vbCritical, "SolRatio v" & GetVersion()
End Sub

Sub LanciaSensitivita()
    ' Flusso:
    '   1. Se il foglio Sensitivita_Config non esiste -> crealo e fermati
    '   2. Se esiste -> leggi la configurazione e lancia Python
    
    Dim title As String: title = "SolRatio v" & GetVersion() & " - Sensitivita"
    Dim ws As Worksheet
    Dim sheetExists As Boolean: sheetExists = False
    Dim s As Worksheet
    For Each s In ThisWorkbook.Sheets
        If s.Name = "Sensitivita_Config" Then sheetExists = True: Exit For
    Next
    
    If Not sheetExists Then
        ' Prima volta: crea il foglio di configurazione
        CreaSensitivitaConfig
        MsgBox "Foglio 'Sensitivita_Config' creato." & vbCrLf & vbCrLf & _
               "1. Metti X nella colonna A per selezionare i parametri" & vbCrLf & _
               "2. Modifica i range Min/Max se necessario" & vbCrLf & _
               "3. Imposta Metodo, Livelli, Delta%, Coltura in basso" & vbCrLf & _
               "4. Premi di nuovo il pulsante Sensitivita per lanciare", _
               vbInformation, title
        Exit Sub
    End If
    
    ' Foglio esiste: leggi configurazione e lancia
    Set ws = ThisWorkbook.Sheets("Sensitivita_Config")
    
    ' Verifica prerequisiti
    Dim engineDir As String: engineDir = GetEngineDir()
    If engineDir = "" Then
        MsgBox "Engine non trovata.", vbCritical, title
        Exit Sub
    End If
    Dim projDir As String: projDir = GetProjDir()
    If projDir = "" Then
        MsgBox "Percorso non determinabile.", vbExclamation, title
        Exit Sub
    End If
    
    ' Cerca SolRatio_progetto con entrambe le estensioni
    Dim projFile As String
    If Dir(projDir & "SolRatio_progetto.xlsm") <> "" Then
        projFile = projDir & "SolRatio_progetto.xlsm"
    ElseIf Dir(projDir & "SolRatio_progetto.xlsx") <> "" Then
        projFile = projDir & "SolRatio_progetto.xlsx"
    Else
        MsgBox "SolRatio_progetto non trovato.", vbCritical, title
        Exit Sub
    End If
    If Dir(projDir & "risultati.xlsx") = "" Then
        MsgBox "risultati.xlsx non trovato." & vbCrLf & _
               "Eseguire prima il calcolo principale.", vbExclamation, title
        Exit Sub
    End If
    
    ' ---- Aggiorna valori base dal foglio Parametri (M1) ----
    Dim wsParam As Worksheet
    Set wsParam = ThisWorkbook.Sheets("Parametri")
    Dim cellMap As Object
    Set cellMap = CreateObject("Scripting.Dictionary")
    cellMap("pitch") = "B15": cellMap("W") = "B16"
    cellMap("H_min_terra") = "B17": cellMap("beta_max") = "B18"
    cellMap("sanu") = "B33": cellMap("albedo") = "B24"
    cellMap("tau") = "B23": cellMap("backtracking") = "B19"
    cellMap("slope_pct") = "B6": cellMap("slope_azimuth") = "B7"
    cellMap("axis_azimuth") = "B14"
    cellMap("lat") = "B4": cellMap("lon") = "B5"
    cellMap("n_ext") = "B44"
    cellMap("theta_fix") = "B20"
    cellMap("n_sub") = "B47"

    Dim ri As Long
    For ri = 4 To 19
        Dim ky As String: ky = Trim(CStr(ws.Cells(ri, 2).Value & ""))
        If cellMap.Exists(ky) Then
            Dim bv As Variant
            On Error Resume Next
            bv = wsParam.Range(cellMap(ky)).Value
            On Error GoTo 0
            If Not IsEmpty(bv) Then ws.Cells(ri, 6).Value = bv
        End If
    Next ri
    
    ' ---- Leggi parametri selezionati (righe 4..16, colonna A=X, B=chiave, D=min, E=max) ----
    Dim paramsStr As String: paramsStr = ""
    Dim nSel As Long: nSel = 0
    Dim hasPVGIS As Boolean: hasPVGIS = False
    Dim i As Long
    Dim sel As String
    Dim pKey As String, pMin As String, pMax As String
    Dim defMin As String, defMax As String
    
    For i = 4 To 18
        sel = UCase(Trim(CStr(ws.Cells(i, 1).Value & "")))
        If sel = "X" Then
            nSel = nSel + 1
            pKey = Trim(CStr(ws.Cells(i, 2).Value))
            pMin = Trim(CStr(ws.Cells(i, 4).Value))
            pMax = Trim(CStr(ws.Cells(i, 5).Value))
            defMin = Trim(CStr(ws.Cells(i, 7).Value))
            defMax = Trim(CStr(ws.Cells(i, 8).Value))
            
            If paramsStr <> "" Then paramsStr = paramsStr & ";"

            ' Se Min/Max uguali ai default, non passare il range
            If pMin = defMin And pMax = defMax Then
                paramsStr = paramsStr & pKey
            Else
                ' Forza punto decimale per Python (locale IT usa virgola)
                paramsStr = paramsStr & pKey & ":" & _
                    Replace(pMin, ",", ".") & ":" & Replace(pMax, ",", ".")
            End If
            
            If pKey = "lat" Or pKey = "lon" Then hasPVGIS = True
        End If
    Next
    
    If nSel = 0 Then
        MsgBox "Nessun parametro selezionato." & vbCrLf & _
               "Metti X nella colonna A del foglio Sensitivita_Config.", _
               vbExclamation, title
        Exit Sub
    End If
    
    ' Warning PVGIS
    If hasPVGIS Then
        If MsgBox("Lat/Lon richiedono ri-download PVGIS per ogni livello." & vbCrLf & _
                  "L'analisi sara significativamente piu lenta." & vbCrLf & vbCrLf & _
                  "Continuare?", vbYesNo + vbExclamation, title) = vbNo Then Exit Sub
    End If
    
    ' ---- Leggi impostazioni generali (riga 19..22) ----
    Dim method As String: method = LCase(Trim(CStr(ws.Cells(19, 3).Value & "")))
    If method = "" Then method = "both"
    If method <> "oat" And method <> "morris" And method <> "both" Then
        MsgBox "Metodo non valido: '" & method & "'. Usare oat, morris o both.", vbExclamation, title
        Exit Sub
    End If
    
    Dim nLevels As Long: nLevels = Val(ws.Cells(20, 3).Value)
    If nLevels < 1 Or nLevels > 20 Then nLevels = 5
    
    Dim deltaTornado As Double: deltaTornado = Val(ws.Cells(21, 3).Value) / 100#
    If deltaTornado < 0.01 Or deltaTornado > 1# Then deltaTornado = 0.2
    
    Dim cropName As String: cropName = LCase(Trim(CStr(ws.Cells(22, 3).Value & "")))
    If cropName = "" Then cropName = "foraggere"
    
    Dim morrisR As Long: morrisR = Val(ws.Cells(23, 3).Value)
    If morrisR < 2 Or morrisR > 100 Then morrisR = 10
    
    ' ---- Stima run e conferma ----
    Dim nCont As Long: nCont = nSel
    ' Backtracking e discreto: controlla se selezionato
    If UCase(Trim(CStr(ws.Cells(11, 1).Value & ""))) = "X" Then nCont = nCont - 1
    
    Dim runsOAT As Long, runsMorris As Long
    If method = "oat" Or method = "both" Then
        runsOAT = nCont * (2 * nLevels + 1 + 2)
        If UCase(Trim(CStr(ws.Cells(11, 1).Value & ""))) = "X" Then runsOAT = runsOAT + 2
    End If
    If method = "morris" Or method = "both" Then
        If nCont > 0 Then runsMorris = morrisR * (nCont + 1)
    End If
    Dim totalRuns As Long: totalRuns = runsOAT + runsMorris
    
    Dim nPVGIS As Long: nPVGIS = 0
    If hasPVGIS Then nPVGIS = 1
    If UCase(Trim(CStr(ws.Cells(15, 1).Value & ""))) = "X" And _
       UCase(Trim(CStr(ws.Cells(16, 1).Value & ""))) = "X" Then nPVGIS = 2
    Dim fracP As Double
    If nSel > 0 Then fracP = CDbl(nPVGIS) / CDbl(nSel) Else fracP = 0
    Dim timeMin As Long
    timeMin = CLng(totalRuns * (fracP * 5# + (1# - fracP) * 0.5) / 60)
    If timeMin < 1 And totalRuns > 0 Then timeMin = 1
    
    Dim summary As String
    summary = "ANALISI SENSITIVITA" & vbCrLf & vbCrLf & _
              "Metodo: " & UCase(method) & vbCrLf & _
              "Parametri: " & nSel & " selezionati" & vbCrLf & _
              "Coltura: " & cropName & vbCrLf & _
              "Livelli OAT: " & CStr(2 * nLevels + 1) & vbCrLf & _
              "Traiettorie Morris: " & CStr(morrisR) & vbCrLf & _
              "Delta tornado: +/-" & Format(deltaTornado * 100, "0") & "%" & vbCrLf & _
              "Run stimati: ~" & totalRuns & " (~" & timeMin & " min)" & vbCrLf & vbCrLf & _
              "Lanciare?"
    
    If MsgBox(summary, vbOKCancel + vbInformation, title) = vbCancel Then Exit Sub
    
    ' ---- Costruisci e lancia ----
    Dim pythonExe As String: pythonExe = GetPythonExe()
    Dim batPath As String: batPath = engineDir & "_br_run.bat"
    Dim logPath As String: logPath = projDir & "sensitivity_log.txt"
    
    Dim cmdArgs As String
    cmdArgs = " --method " & method & _
              " --params " & paramsStr & _
              " --levels " & CStr(nLevels) & _
              " --delta_tornado " & Replace(Format(deltaTornado, "0.00"), ",", ".") & _
              " --crop " & cropName & _
              " --morris_r " & CStr(morrisR)
    
    Dim fNum As Integer: fNum = FreeFile
    Open batPath For Output As #fNum
    Print #fNum, "@echo off"
    Print #fNum, "cd /d """ & engineDir & """"
    Print #fNum, """" & pythonExe & """ solratio_sensitivity.py """ & projFile & """" & cmdArgs & " > """ & logPath & """ 2>&1"
    Print #fNum, "echo."
    Print #fNum, "echo Completato. Premi un tasto per chiudere."
    Print #fNum, "pause > nul"
    Close #fNum
    
    Shell "cmd /c """ & batPath & """", 1
    MsgBox "Analisi avviata. Attendere il completamento nella finestra cmd." & vbCrLf & _
           "I risultati saranno aggiunti a risultati.xlsx.", vbInformation, title
End Sub


Private Sub CreaSensitivitaConfig()
    ' Crea (o ricrea) il foglio Sensitivita_Config con tabella parametri e impostazioni
    
    Dim ws As Worksheet
    Dim exists As Boolean: exists = False
    Dim s As Worksheet
    For Each s In ThisWorkbook.Sheets
        If s.Name = "Sensitivita_Config" Then exists = True: Set ws = s: Exit For
    Next
    
    If Not exists Then
        Set ws = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = "Sensitivita_Config"
    Else
        ws.Cells.Clear
    End If
    
    ' Stili
    Dim hdrFont As Object, hdrFill As Long, catFill As Long
    
    ' Colonne
    ws.Columns("A").ColumnWidth = 10  ' Seleziona
    ws.Columns("B").ColumnWidth = 22  ' Chiave Python
    ws.Columns("C").ColumnWidth = 26  ' Parametro
    ws.Columns("D").ColumnWidth = 12  ' Min
    ws.Columns("E").ColumnWidth = 12  ' Max
    ws.Columns("F").ColumnWidth = 14  ' Valore base
    ws.Columns("G").ColumnWidth = 12  ' Default Min
    ws.Columns("H").ColumnWidth = 12  ' Default Max
    
    ' Titolo
    ws.Range("A1").Value = "CONFIGURAZIONE ANALISI SENSITIVITA"
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Size = 12
    ws.Range("A1").Font.Color = RGB(255, 255, 255)
    ws.Range("A1:H1").Interior.Color = RGB(31, 78, 121)
    ws.Rows(1).RowHeight = 28
    
    ws.Range("A2").Value = "Metti X nella colonna A per selezionare. Modifica Min/Max a piacere. Poi premi il pulsante Sensitivita."
    ws.Range("A2").Font.Italic = True
    ws.Range("A2").Font.Size = 9
    
    ' Header tabella
    Dim headers As Variant
    headers = Array("Seleziona", "Chiave", "Parametro", "Min", "Max", "Valore base", "Def.Min", "Def.Max")
    Dim c As Long
    For c = 0 To 7
        ws.Cells(3, c + 1).Value = headers(c)
        ws.Cells(3, c + 1).Font.Bold = True
        ws.Cells(3, c + 1).Font.Color = RGB(255, 255, 255)
        ws.Cells(3, c + 1).Interior.Color = RGB(46, 117, 182)
        ws.Cells(3, c + 1).HorizontalAlignment = xlCenter
    Next
    
    ' Parametri: chiave, label, min_default, max_default, cella_base, categoria
    Dim pData(1 To 16, 1 To 5) As Variant
    pData(1, 1) = "pitch": pData(1, 2) = "Pitch [m]": pData(1, 3) = 3: pData(1, 4) = 20: pData(1, 5) = "B15"
    pData(2, 1) = "W": pData(2, 2) = "W modulo [m]": pData(2, 3) = 1.5: pData(2, 4) = 6: pData(2, 5) = "B16"
    pData(3, 1) = "H_min_terra": pData(3, 2) = "H min terra [m]": pData(3, 3) = 0: pData(3, 4) = 5: pData(3, 5) = "B17"
    pData(4, 1) = "beta_max": pData(4, 2) = "Beta max [deg]": pData(4, 3) = 30: pData(4, 4) = 65: pData(4, 5) = "B18"
    pData(5, 1) = "sanu": pData(5, 2) = "SANU [m]": pData(5, 3) = 0: pData(5, 4) = 2: pData(5, 5) = "B33"
    pData(6, 1) = "albedo": pData(6, 2) = "Albedo": pData(6, 3) = 0.1: pData(6, 4) = 0.4: pData(6, 5) = "B24"
    pData(7, 1) = "tau": pData(7, 2) = "Trasmittanza tau": pData(7, 3) = 0: pData(7, 4) = 1: pData(7, 5) = "B23"
    pData(8, 1) = "backtracking": pData(8, 2) = "Mod. tracker (0/1/2)": pData(8, 3) = 0: pData(8, 4) = 2: pData(8, 5) = "B19"
    pData(9, 1) = "slope_pct": pData(9, 2) = "Pendenza [%]": pData(9, 3) = 0: pData(9, 4) = 30: pData(9, 5) = "B6"
    pData(10, 1) = "slope_azimuth": pData(10, 2) = "Azimut discesa [deg]": pData(10, 3) = 0: pData(10, 4) = 360: pData(10, 5) = "B7"
    pData(11, 1) = "axis_azimuth": pData(11, 2) = "Azimut asse tracker [deg]": pData(11, 3) = 0: pData(11, 4) = 360: pData(11, 5) = "B14"
    pData(12, 1) = "lat": pData(12, 2) = "Latitudine [deg]  ** LENTO **": pData(12, 3) = -65: pData(12, 4) = 65: pData(12, 5) = "B4"
    pData(13, 1) = "lon": pData(13, 2) = "Longitudine [deg]  ** LENTO **": pData(13, 3) = -180: pData(13, 4) = 180: pData(13, 5) = "B5"
    pData(14, 1) = "n_ext": pData(14, 2) = "N tracker per lato": pData(14, 3) = 1: pData(14, 4) = 6: pData(14, 5) = "B44"
    pData(15, 1) = "theta_fix": pData(15, 2) = "Theta fisso [deg]": pData(15, 3) = -60: pData(15, 4) = 60: pData(15, 5) = "B20"
    pData(16, 1) = "n_sub": pData(16, 2) = "N sub-sampling orario": pData(16, 3) = 1: pData(16, 4) = 60: pData(16, 5) = "B47"
    
    ' Categorie: riga iniziale, colore
    Dim catRows As Variant: catRows = Array(4, 9, 12, 15)
    Dim catNames As Variant: catNames = Array("STRUTTURALI", "OTTICI", "TERRENO / ASSE", "GEOGRAFICI (PVGIS)")
    Dim catColor As Long: catColor = RGB(189, 215, 238)
    
    ' Inserisci le righe con categoria come sfondo sulla prima cella della sezione
    Dim row As Long: row = 4
    Dim pi As Long
    Dim wsParam As Worksheet
    Set wsParam = ThisWorkbook.Sheets("Parametri")
    
    For pi = 1 To 16
        ' Colonna A: vuota (utente mette X)
        ws.Cells(row, 1).Value = ""
        ws.Cells(row, 1).HorizontalAlignment = xlCenter
        ws.Cells(row, 1).Font.Bold = True
        ws.Cells(row, 1).Font.Size = 12
        
        ' Colonna B: chiave Python
        ws.Cells(row, 2).Value = pData(pi, 1)
        ws.Cells(row, 2).Font.Size = 9
        
        ' Colonna C: label
        ws.Cells(row, 3).Value = pData(pi, 2)
        ws.Cells(row, 3).Font.Size = 10
        
        ' Colonna D: Min (editabile, inizializzato al default)
        ws.Cells(row, 4).Value = pData(pi, 3)
        ws.Cells(row, 4).HorizontalAlignment = xlCenter
        
        ' Colonna E: Max (editabile)
        ws.Cells(row, 5).Value = pData(pi, 4)
        ws.Cells(row, 5).HorizontalAlignment = xlCenter
        
        ' Colonna F: valore base dal foglio Parametri
        Dim baseVal As Variant
        On Error Resume Next
        baseVal = wsParam.Range(pData(pi, 5)).Value
        On Error GoTo 0
        If IsEmpty(baseVal) Then baseVal = "-"
        ws.Cells(row, 6).Value = baseVal
        ws.Cells(row, 6).HorizontalAlignment = xlCenter
        ws.Cells(row, 6).Font.Bold = True
        ws.Cells(row, 6).Interior.Color = RGB(226, 239, 218)
        
        ' Colonne G-H: default Min/Max (nascosti, per confronto)
        ws.Cells(row, 7).Value = pData(pi, 3)
        ws.Cells(row, 7).Font.Color = RGB(180, 180, 180)
        ws.Cells(row, 7).HorizontalAlignment = xlCenter
        ws.Cells(row, 8).Value = pData(pi, 4)
        ws.Cells(row, 8).Font.Color = RGB(180, 180, 180)
        ws.Cells(row, 8).HorizontalAlignment = xlCenter
        
        ' Colorazione righe categoria
        If pi <= 5 Then
            ' Strutturali: nessun colore speciale
        ElseIf pi <= 8 Then
            ws.Range(ws.Cells(row, 2), ws.Cells(row, 3)).Interior.Color = RGB(242, 242, 242)
        ElseIf pi <= 11 Then
            ws.Range(ws.Cells(row, 2), ws.Cells(row, 3)).Interior.Color = RGB(255, 242, 204)
        Else
            ws.Range(ws.Cells(row, 2), ws.Cells(row, 3)).Interior.Color = RGB(244, 204, 204)
        End If
        
        row = row + 1
    Next
    
    ' ---- Separatore ----
    row = 18
    ws.Range(ws.Cells(row, 1), ws.Cells(row, 8)).Interior.Color = RGB(31, 78, 121)
    ws.Cells(row, 1).Value = "IMPOSTAZIONI GENERALI"
    ws.Cells(row, 1).Font.Bold = True
    ws.Cells(row, 1).Font.Color = RGB(255, 255, 255)
    
    ' ---- Impostazioni generali (righe 19-22, colonna B=label, C=valore) ----
    ws.Cells(19, 2).Value = "Metodo (oat / morris / both):"
    ws.Cells(19, 3).Value = "both"
    ws.Cells(19, 2).Font.Bold = True
    
    ws.Cells(20, 2).Value = "Livelli OAT per lato (5=11 tot):"
    ws.Cells(20, 3).Value = 5
    ws.Cells(20, 2).Font.Bold = True
    
    ws.Cells(21, 2).Value = "Delta % tornado:"
    ws.Cells(21, 3).Value = 20
    ws.Cells(21, 2).Font.Bold = True
    
    ws.Cells(22, 2).Value = "Coltura:"
    ws.Cells(22, 3).Value = "foraggere"
    ws.Cells(22, 2).Font.Bold = True
    
    ' Lista colture come nota
    ws.Cells(22, 4).Value = "foraggere, cereali_C3, mais, ortaggi_foglia, ortaggi_frutto, leguminose_granella, tuberi_radici, frutta, bacche"
    ws.Cells(22, 4).Font.Size = 8
    ws.Cells(22, 4).Font.Color = RGB(128, 128, 128)
    
    ws.Cells(23, 2).Value = "Traiettorie Morris (r):"
    ws.Cells(23, 3).Value = 10
    ws.Cells(23, 2).Font.Bold = True
    ws.Cells(23, 4).Value = "2-100, default 10. Piu traiettorie = statistiche piu precise ma piu tempo."
    ws.Cells(23, 4).Font.Size = 8
    ws.Cells(23, 4).Font.Color = RGB(128, 128, 128)
    
    ' Tab color
    ws.Tab.Color = RGB(112, 48, 160)
    
    ' Attiva il foglio
    ws.Activate
    ws.Range("A4").Select
End Sub

Private Sub FormatButton(btn As Shape, sName As String, sMacro As String, sText As String)
    Dim i As Integer
    With btn
        .Name = sName: .OnAction = sMacro
        .Fill.Visible = msoTrue: .Fill.ForeColor.RGB = RGB(31, 78, 121)
        .Line.Visible = msoFalse
        With .TextFrame2
            .TextRange.Text = sText
            .TextRange.Font.Bold = msoTrue: .TextRange.Font.Size = 11
            .TextRange.Font.Fill.ForeColor.RGB = RGB(255, 255, 255)
            For i = 1 To .TextRange.Paragraphs.Count
                .TextRange.Paragraphs(i).ParagraphFormat.Alignment = msoAlignCenter
            Next i
            .VerticalAnchor = msoAnchorMiddle
        End With
        .Shadow.Visible = msoTrue
    End With
End Sub

Sub TestPython()
    Dim engineDir As String, pythonExe As String
    Dim batPath As String, pyPath As String, logPath As String, dbgPath As String
    Dim fNum As Integer
    
    engineDir = GetEngineDir()
    If engineDir = "" Then
        MsgBox "Engine non trovata." & vbCrLf & _
               "Progetto: " & GetProjDir() & vbCrLf & _
               "Path: " & ThisWorkbook.Path, _
               vbCritical, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    pythonExe = GetPythonExe()
    batPath = engineDir & "_br_run.bat"
    pyPath = engineDir & "br_test_tmp.py"
    logPath = engineDir & "br_test.txt"
    dbgPath = engineDir & "br_test.dbg"
    
    On Error Resume Next
    Kill batPath: Kill pyPath: Kill logPath: Kill dbgPath
    On Error GoTo 0
    
    fNum = FreeFile
    Open pyPath For Output As #fNum
    Print #fNum, "import sys"
    Print #fNum, "dbg=open(r'" & dbgPath & "','w')"
    Print #fNum, "log=open(r'" & logPath & "','w')"
    Print #fNum, "dbg.write('S1\n');dbg.flush()"
    Print #fNum, "log.write('Python: '+sys.version[:30]+'\n')"
    Print #fNum, "errori=0"
    Print #fNum, "for m in ['numpy','pandas','pvlib','bifacial_radiance','openpyxl','lxml']:"
    Print #fNum, "    dbg.write('S2 '+m+'\n');dbg.flush()"
    Print #fNum, "    try:"
    Print #fNum, "        mod=__import__(m);v=getattr(mod,'__version__','n/a')"
    Print #fNum, "        log.write('  '+m+': '+v+'\n')"
    Print #fNum, "    except Exception as e:"
    Print #fNum, "        log.write('  '+m+': ERRORE '+str(e)+'\n');errori+=1"
    Print #fNum, "try:"
    Print #fNum, "    import reportlab;log.write('  reportlab: '+reportlab.Version+'\n')"
    Print #fNum, "except: log.write('  reportlab: non installato (opzionale, per PDF)\n')"
    Print #fNum, "if errori==0:"
    Print #fNum, "    log.write('\nRISULTATO: OK\n')"
    Print #fNum, "else:"
    Print #fNum, "    log.write('\nRISULTATO: FAIL ('+str(errori)+' moduli mancanti)\n')"
    Print #fNum, "    log.write('Installa con: pip install numpy pandas pvlib bifacial_radiance openpyxl lxml\n')"
    Print #fNum, "log.close()"
    Print #fNum, "dbg.write('S3\n');dbg.close()"
    Close #fNum
    
    fNum = FreeFile
    Open batPath For Output As #fNum
    Print #fNum, "@echo off"
    Print #fNum, Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & pyPath & Chr(34)
    Close #fNum
    
    Shell "cmd /c " & Chr(34) & batPath & Chr(34), 1
    MsgBox "Test avviato. Attendi cmd, poi Alt+F8 > LeggiRisultatoTest.", vbInformation, "SolRatio v" & GetVersion()
End Sub

Sub LeggiRisultatoTest()
    Dim engineDir As String, logPath As String, dbgPath As String
    Dim logMsg As String, logLine As String, fNum As Integer
    
    engineDir = GetEngineDir()
    If engineDir = "" Then MsgBox "Engine non trovata.", vbCritical, "SolRatio v" & GetVersion(): Exit Sub
    logPath = engineDir & "br_test.txt"
    dbgPath = engineDir & "br_test.dbg"
    
    If Dir(logPath) = "" Then
        logMsg = ""
        If Dir(dbgPath) <> "" Then
            fNum = FreeFile: Open dbgPath For Input As #fNum
            Do While Not EOF(fNum): Line Input #fNum, logLine: logMsg = logMsg & logLine & vbCrLf: Loop
            Close #fNum
        End If
        If logMsg = "" Then logMsg = "(nessun file)"
        MsgBox "Test non trovato." & vbCrLf & logMsg, vbExclamation, "SolRatio v" & GetVersion()
        Exit Sub
    End If
    
    logMsg = "": fNum = FreeFile: Open logPath For Input As #fNum
    Do While Not EOF(fNum): Line Input #fNum, logLine: logMsg = logMsg & logLine & vbCrLf: Loop
    Close #fNum
    
    If InStr(logMsg, "RISULTATO: OK") > 0 Then
        MsgBox logMsg, vbInformation, "Test OK"
    Else
        MsgBox logMsg, vbExclamation, "Moduli mancanti"
    End If
    
    On Error Resume Next
    Kill logPath: Kill dbgPath
    Kill engineDir & "br_test_tmp.py": Kill engineDir & "_br_run.bat"
    On Error GoTo 0
End Sub
