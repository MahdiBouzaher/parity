Sub Provisions()
  Dim i As Long, total As Double
  For i = 2 To lastRow
    rate = Cells(i, 2) * Cells(i, 3)
    Cells(i, 5) = Cells(i, 4) * rate
    total = total + Cells(i, 5)
  Next i
  Cells(1, 7) = total / (lastRow - 1)
End Sub
