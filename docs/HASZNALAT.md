# HP Scan: használat Fedora alatt

## Indítás másik gépen

Az alkalmazás x86_64 architektúrájú Fedora gépre készült. A grafikus program,
a Python és a kép/PDF könyvtárak a hordozható csomagban vannak.
A scanner illesztőprogramja a használati gépre telepítendő:

```bash
sudo dnf install sane-backends sane-airscan hplip hplip-libs
```

Indítás a letöltött fájl könyvtárában:

```bash
chmod +x FedoraMultiScan-1.0.0-x86_64.AppImage
./FedoraMultiScan-1.0.0-x86_64.AppImage
```

Ha a FUSE miatti csatolás nem működik:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./FedoraMultiScan-1.0.0-x86_64.AppImage
```

Másik lehetőség a tar.gz csomag. Ez nem igényel FUSE-t:

```bash
tar -xzf FedoraMultiScan-1.0.0-x86_64.tar.gz
./FedoraMultiScan-1.0.0.AppDir/AppRun
```

Próbaüzem: pipáld be a „Próbaüzem, scanner nélkül” lehetőséget, vagy indítsd
`--demo` kapcsolóval. A próbaüzem is valódi képeket és PDF-eket készít,
egyértelműen jelölt szimulált lapokból. Külön tesztmappát válassz hozzá.

## A munka menete

1. Válaszd ki a scannert az „Eszközök keresése” gombbal. Ha szükséges,
   add meg közvetlenül a SANE-azonosítót. Az eszköz beállításainak lekérése
   frissíti az elérhető színmódokat és beolvasási forrásokat.
2. Állítsd be a méretet, az álló/fekvő tájolást és a felbontást (alapból
   600 dpi). A JPG/PNG mellett minden esetben PDF is készül.
3. Válaszd ki a célmappát és az automatikus vagy egyedi előtagokat.
   Opcionálisan add meg az egységenkénti oldalszámot és a csoportosítást.
4. A „Munka előkészítése” létrehozza az első egységet. Egyedi előtagnál
   megkérdezi a nevet. **Ekkor még nincs beolvasás.**
5. Tedd az első lapot az üvegre, majd nyomj `Space`-t vagy `T`-t,
   vagy kattints a „Tovább” gombra. Egy művelet egyetlen oldalt olvas be.
6. Lapcsere után ismét `Space` / `T`. Új dolgozat előtt `U`.
7. A munka végén `V`, `Esc` vagy a „Vége” gomb zárja le a munkát.

| Művelet | Billentyű |
| --- | --- |
| Egy lap beolvasása | `Space`, `T`, `Ctrl+Enter` |
| Új egység előkészítése, beolvasás nélkül | `U`, `Ctrl+N` |
| Munka lezárása | `V`, `Esc`, `Ctrl+Q` |
| Név elfogadása a bekérő ablakban | `Enter` |
| Névbekérés megszakítása | `Esc` |

A névmező azonnal aktív. A névben szóköz, illetve t/u/v betű is használható:
a munka gyorsbillentyűi a névbekérő ablakban nem működnek.
**A név Enterrel elfogadása soha nem indít beolvasást.** Helyezd el a lapot,
majd külön nyomj `Space`-t. Ez az automatikus oldalszámhatár után is így van.
Az automatikus csoportosítás nem jelent automatikus lapbeolvasást.

## Mappák és fájlok

Alapértelmezett elrendezés:

```text
kivalasztott_mappa/
  aa.pdf
  ab.pdf
  images/
    aa_001.jpg
    aa_002.jpg
    ab_001.jpg
```

Csoportosítás esetén:

```text
kivalasztott_mappa/
  aa/
    aa.pdf
    aa_001.jpg
    aa_002.jpg
  ab/
    ab.pdf
    ab_001.jpg
```

Egyedi előtagnál az `aa` helyén például `Pistike` szerepel a mappa, a PDF
és minden kép nevében is. Az ékezetek és a szóközök használhatók.
Az automatikus sorrend aa, ab, …, az, ba, …, zz, aaa, aab, …;
foglalt névnél a program továbblép. Egyedi névnél másik nevet kér.
Meglévő munkát nem folytat rá automatikusan egy új munkára.

Ötoldalas egységméretnél az ötödik lap után az egység megtelik.
A következő beolvasási művelet automatikus előtag esetén az új egységbe
ment. Egyedi előtag esetén előbb bekéri a következő nevet, majd vár
egy újabb `Space` / `T` műveletre. Az utolsó, rövidebb egység is megmarad.
Az „Új egység” korábban is lezárhat egy egységet; a számláló újraindul.

## Tájolás és lapméret

Az M130nw síkágyas, nem lapadagolós scanner. A legnagyobb beolvasható
felület 215,9 × 297 mm. Az A3 nem fér rá; az egyedi méretet is ezen belül
lehet megadni. A rövid oldalt add meg szélességként, a hosszabbat magasságként.

Mindig a lap rövid oldala legyen az üveg szélességén. Fekvő lapnál
a szöveg teteje az üveg jobb széle felé nézzen: mentéskor a program 90 fokkal
balra forgatja a képet, és a PDF is fekvő lesz. Nem szövegfelismerés alapján
dönt a tájolásról. A képek és a PDF fizikai méretét a kért dpi határozza meg.

## Megszakítás és folytatás

A PDF minden sikeresen mentett oldal után frissül. Az egyes képek
átmeneti fájlba készülnek, és csak teljes mentés után kapják meg a végleges
nevüket. A `.hpscan` rejtett mappa a munkanaplót és az ideiglenes fájlokat
tartalmazza. Ne töröld, ha folytatni szeretnéd a munkát.

Az ablak bezárása félbehagyja a munkát. Ugyanazt a célmappát választva
a program felajánlja a legutóbbi félbehagyott munka folytatását az eredeti
beállításokkal. A „Vége” lezárja a munkanaplót. A PDF-ek és a képek a szokásos
alkalmazásokkal a munkanaplótól függetlenül is megnyithatók.

A beolvasás külön megszakítható. A már megkezdett kép/PDF mentés befejeződik.
Mentési hiba után a program megőrzi a mentett képet, lehetőség szerint a nyers
beolvasást is, és kiírja az elérési útját. A nyers fájl `.pnm` kiterjesztésű;
próbaüzemben a tartalma PNG. A félbemaradt PDF-et a következő művelet vagy
a munkafolytatás újraépíti a képekből.

## Első valódi készülékpróba

Kapcsold be a scannert, csatlakoztasd USB-n vagy ugyanarra a hálózatra, majd:

```bash
scanimage -L
```

Ha a HPLIP hiányzó HP bővítményt jelez, indítsd a `hp-plugin -i` parancsot.
A HP licencét a használati gépen kell elfogadni. Hálózaton szükség esetén
`hp-setup -i SCANNER_IP` segíthet. A teljes `hpaio:/net/...` azonosító
kézzel is beírható az alkalmazásba. eSCL/WSD eszközt is lehet választani,
ha a SANE felismeri; a konkrét készülék támogatása hardverpróbát igényel.

Az M130nw a teljes A4-es, 600 dpi-s színes lapot a SANE-en át (JPEG-ként)
nem tudja leadni: kb. 40 másodperc után „Device busy” hibával megszakítja.
Ezért ha az eszköz név szerint szerepel az `/etc/sane.d/airscan.conf`
`[devices]` szakaszában, a program közvetlenül, PDF-ként kéri le a lapot,
így a 600 dpi színes is működik (kb. 50 másodperc laponként). Példa:

```ini
[devices]
"HP LaserJet M130nw (eSCL)" = http://Nyomda.local/eSCL/, escl
```

Automatikusan felderített (a fájlban nem szereplő) eszköznél marad a SANE;
ott színesben 300 dpi-t, 600 dpi-hez szürkeárnyalatot válassz.

Először egy A4-es tesztlappal próbálj 300 és 600 dpi-t, álló és fekvő
tájolást, majd két külön egységet. Ellenőrizd a teljes lapot, az oldalsorrendet,
a kép/PDF méretét és a nevek helyességét. A backend nem minden felbontást
és színmódot támogat. A program hibát jelez, ha a scanner más felbontást
vagy méretet adott vissza a kért helyett.

Fejlesztés és helyi ellenőrzés: Fedora 44 x86_64. Fedora 45 konténerben
az AppImage mentési próbája és a grafikus felület kijelző nélküli indítása
is lefutott. Valódi HP M130nw-vel Fedora 45-ön a beolvasás 300 és 600 dpi-n
ellenőrizve; a teljes felületi munkamenet próbája még hátravan. A betűkészletekhez a rendszer fontconfig
könyvtárát és beállításait használja az alkalmazás.
