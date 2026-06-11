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
    '    URL tipico: https://d.docs.live.net/XXXXXXXX/Documenti/<cartella>/...
    '    Locale:     C:\Users\<utente>\OneDrive\Documenti\<cartella>/...
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
