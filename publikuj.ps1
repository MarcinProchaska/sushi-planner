# ---------------------------------------------------------------------------
# Sushi Planner — publikacja zmian na GitHuba (Windows).
#
# To samo, co robi publikuj.command na Macu: porównuje pliki w tym folderze
# z tym, co leży na GitHubie, i wysyła tylko te, które się różnią. Niczego nie
# kasuje. Porównanie idzie po git-owym SHA blobu, więc identyczny plik nie
# generuje pustego commita.
#
# Uruchamiasz przez publikuj.bat (dwuklik). Ten plik sam z siebie nie wystartuje,
# bo Windows domyślnie blokuje skrypty .ps1 — .bat podaje mu -ExecutionPolicy Bypass.
#
# Zero zależności: czysty PowerShell 5.1 (ten z pudełka) albo 7. Bez gita,
# bez curla, bez lokalnego klona repozytorium.
#
# UWAGA dla edytujących: ten plik MUSI zostać zapisany w UTF-8 ZE ZNACZNIKIEM BOM.
# PowerShell 5.1 bez BOM-u czyta go jako ANSI i polskie litery zamieniają się
# w krzaki — razem z nimi psują się komunikaty, a czasem i składnia.
# ---------------------------------------------------------------------------

$ErrorActionPreference = 'Stop'
# Starsze Windowsy negocjują domyślnie TLS 1.0, którego GitHub już nie przyjmuje.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$OWNER  = 'MarcinProchaska'
$REPO   = 'sushi-planner'
$BRANCH = 'main'
$TOKEN_FILE = Join-Path $env:USERPROFILE '.sushi-github-token'
# $PSScriptRoot jest ustawiane przez sam PowerShell i nie zalezy od tego, czy plik
# uruchomiono przez -File, czy wczytano kropka. Zapas na wszelki wypadek.
$FOLDER = if ($PSScriptRoot) { $PSScriptRoot }
          else { Split-Path -Parent $MyInvocation.MyCommand.Path }

# Czego nie wysyłamy: tokenu, śmieci systemowych i tego, co wypluwają testy. Kropkowce lecą hurtem.
#
# Skryptów publikujących NIE pomijamy — także tego, który właśnie działa.
# Wcześniej każdy pomijał sam siebie, więc publikując z Windowsa nigdy nie dało
# się wysłać publikuj.ps1; plik istniał wyłącznie na jednym dysku i gdy stamtąd
# zniknął, trzeba go było pisać od zera. Plik jest czytany z dysku, nie
# nadpisywany w locie, więc wysłanie samego siebie niczemu nie szkodzi.
function Pomijamy($nazwa) {
  foreach ($w in @('desktop.ini')) { if ($nazwa -eq $w) { return $true } }
  foreach ($w in @('.*', 'Icon*', '*.download', '~$*', 'out_test.*', 'shot-*.png')) {
    if ($nazwa -like $w) { return $true } }
  return $false
}

function Pisz($tekst, $kolor) {
  if ($kolor) { Write-Host $tekst -ForegroundColor $kolor } else { Write-Host $tekst }
}

Write-Host ''
Pisz '  Sushi Planner - publikacja na GitHuba' 'Cyan'
Write-Host '  ------------------------------------------------------------'
Pisz "  Folder: $FOLDER" 'DarkGray'

# --- token -----------------------------------------------------------------
if (-not (Test-Path -LiteralPath $TOKEN_FILE)) {
  Pisz '  Nie znalazlem zapisanego tokenu GitHuba.' 'Yellow'
  Write-Host ''
  Write-Host '  Zrob to raz:'
  Write-Host '   1. Wejdz na https://github.com/settings/personal-access-tokens/new'
  Write-Host '   2. Token name: sushi-planner'
  Write-Host '   3. Expiration: wybierz np. 1 rok'
  Write-Host '   4. Repository access: Only select repositories -> sushi-planner'
  Write-Host '   5. Permissions -> Repository permissions -> Contents: Read and write'
  Write-Host '   6. Generate token i skopiuj go (zaczyna sie od github_pat_)'
  Write-Host ''
  # -AsSecureString, czyli bez echa: wklejony token nie pojawia sie na ekranie
  # i nie zostaje w oknie konsoli, na zrzucie ekranu ani w nagraniu.
  $bezpieczny = Read-Host '  Wklej token tutaj (nie pokaze sie na ekranie)' -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($bezpieczny)
  try   { $wklejony = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  $wklejony = ($wklejony -replace '\s', '')
  if ([string]::IsNullOrEmpty($wklejony)) { Pisz '  Pusty token, przerywam.' 'Red'; exit 1 }

  # Najpierw pusty plik i prawa, potem tresc — inaczej token przez moment lezy
  # czytelny dla kazdego konta na tej maszynie.
  New-Item -ItemType File -Path $TOKEN_FILE -Force | Out-Null
  $acl = Get-Acl -LiteralPath $TOKEN_FILE
  $acl.SetAccessRuleProtection($true, $false)          # zrywamy dziedziczenie
  # @(...) robi kopie listy: bez niej zdejmujemy reguly z kolekcji, po ktorej
  # wlasnie idziemy, i .NET przerywa to wyjatkiem.
  @($acl.Access) | ForEach-Object { $acl.RemoveAccessRule($_) | Out-Null }
  $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
    $env:USERNAME, 'FullControl', 'Allow')))
  Set-Acl -LiteralPath $TOKEN_FILE -AclObject $acl
  [IO.File]::WriteAllText($TOKEN_FILE, $wklejony, (New-Object Text.UTF8Encoding($false)))
  Remove-Variable wklejony
  Pisz "  Token zapisany w $TOKEN_FILE" 'Green'
  Write-Host ''
}
$TOKEN = ([IO.File]::ReadAllText($TOKEN_FILE) -replace '\s', '')

$API = "https://api.github.com/repos/$OWNER/$REPO"
$NAGLOWKI = @{
  'Authorization'        = "Bearer $TOKEN"
  'Accept'               = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
  'User-Agent'           = 'sushi-planner-publish'
}

$script:BLEDY = 0
$script:WYSLANE = 0

function Koniec {
  Write-Host ''
  if ($script:BLEDY -gt 0) { Read-Host '  Cos poszlo nie tak - Enter zamyka' | Out-Null }
  elseif ($script:WYSLANE -eq 0) {
    Pisz '  Nie bylo czego wyslac. Okno zamknie sie za 10 sekund.' 'DarkGray'
    Start-Sleep -Seconds 10
  } else {
    Pisz '  Gotowe. Okno zamknie sie samo za 4 sekundy.' 'DarkGray'
    Start-Sleep -Seconds 4
  }
}

function Zapytaj($metoda, $adres, $cialo) {
  $p = @{ Uri = $adres; Headers = $NAGLOWKI; Method = $metoda; UseBasicParsing = $true;
          TimeoutSec = 60 }
  if ($cialo) { $p.Body = $cialo; $p.ContentType = 'application/json' }
  try {
    $o = Invoke-WebRequest @p
    return @{ kod = [int]$o.StatusCode; tresc = $o.Content }
  } catch {
    $o = $_.Exception.Response
    if ($null -eq $o) { return @{ kod = 0; tresc = $_.Exception.Message } }
    $kod = [int]$o.StatusCode
    $tresc = ''
    try {
      $czyt = New-Object IO.StreamReader($o.GetResponseStream())
      $tresc = $czyt.ReadToEnd(); $czyt.Close()
    } catch { }
    return @{ kod = $kod; tresc = $tresc }
  }
}

# --- czy token ma prawo PISAC ------------------------------------------------
# Samo „czy odczyt dziala" nic tu nie mowi: repozytorium jest publiczne, wiec kazdy
# wazny token je przeczyta — takze taki, ktory nie ma do niego zadnych uprawnien.
# Dlatego pytamy o permissions.push, czyli o to, co GitHub mysli o TYM tokenie
# przy TYM repozytorium.
$odp = Zapytaj 'GET' $API $null
if ($odp.kod -ne 200) {
  Pisz "  Token nie dziala albo nie widzi repozytorium (HTTP $($odp.kod))." 'Red'
  Pisz "  Skasuj plik $TOKEN_FILE i uruchom skrypt ponownie, zeby podac nowy:" 'Red'
  Write-Host "     del `"$TOKEN_FILE`""
  $script:BLEDY = 1; Koniec; exit 1
}
# Nazwa MUSI sie roznic od $REPO czyms wiecej niz wielkoscia liter - patrz uwaga
# przy $shaZdalny nizej.
$infoRepo = $odp.tresc | ConvertFrom-Json
if (-not $infoRepo.permissions.push) {
  Write-Host ''
  Pisz '  Token czyta to repozytorium, ale nie ma prawa do niego pisac.' 'Red'
  Write-Host ''
  Write-Host '  Najczestsza przyczyna: przy zakladaniu tokenu pole Repository access'
  Write-Host '  zostalo na domyslnym "Public Repositories (read-only)". To daje odczyt'
  Write-Host '  wszystkich publicznych repo i zapis do zadnego - a nasze jest publiczne,'
  Write-Host '  wiec odczyt dziala i wyglada, jakby token byl dobry.'
  Write-Host ''
  Write-Host '  Popraw obie rzeczy naraz:'
  Write-Host '   1. https://github.com/settings/tokens?type=beta -> Twoj token -> Edit'
  Write-Host '   2. Repository access: Only select repositories -> sushi-planner'
  Write-Host '   3. Permissions -> Repository permissions -> Contents: Read and write'
  Write-Host '   4. Update token'
  Write-Host ''
  Write-Host '  Potem uruchom skrypt jeszcze raz - zapisanego tokenu nie musisz kasowac.'
  $script:BLEDY = 1; Koniec; exit 1
}

# --- co lezy na GitHubie -----------------------------------------------------
$odp = Zapytaj 'GET' "$API/contents?ref=$BRANCH" $null
$ZDALNE = @{}
if ($odp.kod -eq 200) {
  foreach ($w in ($odp.tresc | ConvertFrom-Json)) { $ZDALNE[$w.name] = $w.sha }
}
if ($ZDALNE.Count -eq 0) { Pisz '  Repozytorium wyglada na puste - wysle wszystko.' 'Yellow' }

# --- porownanie i wysylka ----------------------------------------------------
$BEZ_ZMIAN = 0; $ZNALEZIONE = 0; $ODMOWA = 0
$sha1 = [Security.Cryptography.SHA1]::Create()

foreach ($plik in (Get-ChildItem -LiteralPath $FOLDER -File | Sort-Object Name)) {
  $nazwa = $plik.Name
  if (Pomijamy $nazwa) { continue }
  $ZNALEZIONE++

  # git-owy SHA blobu: sha1("blob <dlugosc>\0" + zawartosc) — dokladnie to, co
  # GitHub oddaje w polu sha, wiec porownanie jest jeden do jednego.
  $bajty = [IO.File]::ReadAllBytes($plik.FullName)
  $naglowek = [Text.Encoding]::ASCII.GetBytes("blob $($bajty.Length)" + [char]0)
  $razem = New-Object byte[] ($naglowek.Length + $bajty.Length)
  [Array]::Copy($naglowek, 0, $razem, 0, $naglowek.Length)
  [Array]::Copy($bajty, 0, $razem, $naglowek.Length, $bajty.Length)
  $lokalne = (($sha1.ComputeHash($razem) | ForEach-Object { $_.ToString('x2') }) -join '')
  # UWAGA: nazwa MUSI sie roznic od $ZDALNE czyms wiecej niz wielkoscia liter.
  # PowerShell nie rozroznia wielkosci liter w nazwach zmiennych, wiec $zdalne
  # i $ZDALNE to JEDNA zmienna: przypisanie podmienialo cala tablice plikow
  # z GitHuba na pojedynczy SHA. Pierwszy plik jeszcze sie porownal, drugi szedl
  # na PUT bez sha (HTTP 422), trzeci indeksowal juz $null. W bashu na Macu te
  # same dwie nazwy sa dwiema roznymi zmiennymi - stad blad przy przepisywaniu.
  $shaZdalny = $ZDALNE[$nazwa]

  if ($shaZdalny -and $shaZdalny -eq $lokalne) {
    Write-Host ("  bez zmian   {0}" -f $nazwa)
    $BEZ_ZMIAN++
    continue
  }

  $cialo = @{ message = "Aktualizacja $nazwa"; branch = $BRANCH
              content = [Convert]::ToBase64String($bajty) }
  if ($shaZdalny) { $cialo.sha = $shaZdalny }
  $odp = Zapytaj 'PUT' "$API/contents/$nazwa" ($cialo | ConvertTo-Json -Compress)

  if ($odp.kod -eq 200 -or $odp.kod -eq 201) {
    Pisz ("  WYSLANO     {0}" -f $nazwa) 'Green'
    $script:WYSLANE++
  } else {
    Pisz ("  BLAD        {0} - HTTP {1}" -f $nazwa, $odp.kod) 'Red'
    try {
      $k = ($odp.tresc | ConvertFrom-Json).message
      if ($k) { Pisz "              $k" 'DarkGray' }
    } catch { }
    if ($odp.kod -eq 403) { $ODMOWA = 1 }
    $script:BLEDY++
  }
}
$sha1.Dispose()

if ($ZNALEZIONE -eq 0) {
  Pisz '  Brak plikow do wyslania.' 'Red'
  $script:BLEDY = 1; Koniec; exit 1
}

Write-Host '  ------------------------------------------------------------'
if ($script:WYSLANE -gt 0) {
  Pisz ("  Wyslano {0} plik(ow), bez zmian: {1}." -f $script:WYSLANE, $BEZ_ZMIAN) 'Green'
  Write-Host ''
  Write-Host '  Serwer zaciagnie to sam dzis w nocy (ok. 4:30).'
  Write-Host '  Zeby od razu, zaloguj sie i wpisz:'
  Pisz '     ssh root@srv103.mikr.us -p 10103' 'Cyan'
  Pisz '     sushi-update' 'Cyan'
} elseif ($script:BLEDY -gt 0) {
  Pisz ("  Nie udalo sie wyslac {0} plik(ow)." -f $script:BLEDY) 'Red'
  # Odczyt zadzialal (sprawdzilismy go na starcie), a zapis nie — to zawsze znaczy
  # to samo: token ma Contents ustawione na Read-only zamiast Read and write.
  if ($ODMOWA -gt 0) {
    Write-Host ''
    Pisz '  HTTP 403 przy zapisie, choc odczyt zadzialal. Token ma prawo czytac,' 'Yellow'
    Pisz '  ale nie pisac - w jego uprawnieniach Contents stoi na Read-only.' 'Yellow'
    Write-Host ''
    Write-Host '  Popraw to tak:'
    Write-Host '   1. https://github.com/settings/tokens?type=beta -> Twoj token -> Edit'
    Write-Host '   2. Permissions -> Repository permissions -> Contents: Read and write'
    Write-Host '   3. Update token'
    Write-Host '  Nowego tokenu nie musisz zakladac - wystarczy zmienic uprawnienie.'
    Write-Host '  Gdybys jednak zakladal nowy, skasuj najpierw zapisany:'
    Write-Host "     del `"$TOKEN_FILE`""
  }
} else {
  Write-Host '  Nic sie nie zmienilo - GitHub ma juz aktualne pliki.'
}

Koniec
