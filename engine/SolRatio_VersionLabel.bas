Attribute VB_Name = "mod_VersionLabel"
'-------------------------------------------------------------------------------
' SolRatio - mod_VersionLabel  (auto-update label versione, item 8 di v4.2)
'
' Aggiorna la cella A1 del foglio "Launcher" leggendo `engine/VERSION` dal
' progetto SolRatio. Il label assume sempre la forma:
'
'   "SOLRATIO AGRIVOLTAICO - Launcher vX.Y.Z"
'
' INSTALLAZIONE (una sola volta per progetto):
'   1) Alt+F11
'   2) File > Importa file... > engine\SolRatio_VersionLabel.bas
'   3) Doppio click su Questa_cartella_di_lavoro (ThisWorkbook) sotto
'      "Microsoft Excel Oggetti" del progetto SolRatio_progetto.xlsm
'   4) Sostituire il contenuto con:
'        Private Sub Workbook_Open()
'            On Error Resume Next
'            UpdateVersionLabelFromFile
'        End Sub
'   5) Ctrl+S, chiudere e riaprire
'
' COMPATIBILITA':
'   - AutoSave ON/OFF: gestito (converte URL OneDrive web in path locale)
'   - OneDrive Personal + OneDrive Business multipli: gestito (prova in
'     sequenza %OneDriveConsumer%, %OneDrive%, %OneDriveCommercial%, e
'     fallback C:\Users\<USER>\OneDrive)
'   - Silent-fail su qualunque errore (non blocca apertura del file)
'   - Idempotente (aggiorna A1 solo se diverso, preserva stato Saved)
'-------------------------------------------------------------------------------

Option Explicit

' Converte un URL OneDrive (es. "https://d.docs.live.net/<id>/...") in path
' locale Windows. Su Windows con piu' OneDrive (Personal + Business),
' prova le env var in ordine e seleziona quella dove la cartella esiste
' davvero. Se l'input e' gia' un path locale, lo restituisce inalterato.
Private Function ResolveLocalPath(ByVal p As String) As String
    Dim s As String
    s = p
    If Len(s) < 4 Then
        ResolveLocalPath = s
        Exit Function
    End If
    If LCase(Left(s, 4)) <> "http" Then
        ResolveLocalPath = s
        Exit Function
    End If

    ' Estrai la sotto-path dopo i primi 4 slash:
    ' "https" + "//" + "host" + "/" + "id" + "/" + sub_path
    Dim slashCount As Integer, idx As Integer, j As Integer
    slashCount = 0
    idx = 0
    For j = 1 To Len(s)
        If Mid(s, j, 1) = "/" Then
            slashCount = slashCount + 1
            If slashCount = 4 Then
                idx = j
                Exit For
            End If
        End If
    Next j
    If idx = 0 Then
        ResolveLocalPath = s
        Exit Function
    End If
    Dim sub_path As String
    sub_path = Mid(s, idx + 1)
    sub_path = Replace(sub_path, "/", "\")

    ' Prova root OneDrive in ordine di probabilita' per file Personal
    Dim od_roots(0 To 3) As String
    od_roots(0) = Environ("OneDriveConsumer")
    od_roots(1) = Environ("OneDrive")
    od_roots(2) = Environ("OneDriveCommercial")
    od_roots(3) = "C:\Users\" & Environ("USERNAME") & "\OneDrive"

    Dim k As Integer, probe As String
    For k = 0 To UBound(od_roots)
        If od_roots(k) <> "" Then
            probe = od_roots(k) & "\" & sub_path
            If Dir(probe, vbDirectory) <> "" Then
                ResolveLocalPath = probe
                Exit Function
            End If
        End If
    Next k

    ' Nessun root ha la cartella: ritorno l'URL originale (la successiva
    ' Dir() fallira' silenziosamente e la macro uscira').
    ResolveLocalPath = s
End Function

Public Sub UpdateVersionLabelFromFile()
    On Error GoTo CleanExit  ' silent-fail a qualsiasi livello

    Dim base_path As String
    base_path = ThisWorkbook.Path
    If Len(base_path) = 0 Then Exit Sub

    ' v4.2 fix: gestisce path OneDrive web -> locale (Personal + Business)
    base_path = ResolveLocalPath(base_path)

    ' Cerca engine/VERSION risalendo la struttura cartelle (max 4 candidati)
    Dim candidates(0 To 3) As String
    candidates(0) = base_path & "\..\..\engine\VERSION"
    candidates(1) = base_path & "\..\engine\VERSION"
    candidates(2) = base_path & "\engine\VERSION"
    candidates(3) = base_path & "\..\..\..\engine\VERSION"

    Dim version_path As String, i As Integer
    version_path = ""
    For i = LBound(candidates) To UBound(candidates)
        If Dir(candidates(i)) <> "" Then
            version_path = candidates(i)
            Exit For
        End If
    Next i
    If version_path = "" Then Exit Sub

    Dim version_text As String, file_num As Integer
    file_num = FreeFile
    Open version_path For Input As #file_num
    Line Input #file_num, version_text
    Close #file_num
    version_text = Trim(version_text)
    If version_text = "" Then Exit Sub

    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets("Launcher")
    On Error GoTo CleanExit
    If ws Is Nothing Then Exit Sub

    Dim new_label As String
    new_label = "SOLRATIO AGRIVOLTAICO - Launcher v" & version_text

    Dim target_cell As Range
    Set target_cell = ws.Range("A1")

    If target_cell.Value <> new_label Then
        Dim was_saved As Boolean
        was_saved = ThisWorkbook.Saved
        target_cell.Value = new_label
        ThisWorkbook.Saved = was_saved
    End If

CleanExit:
    Exit Sub
End Sub
