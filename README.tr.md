# Croow MultiReader

🇬🇧 [English](README.md) · 🇹🇷 Türkçe

**Croow — Alper Pektas tarafından geliştirilmiştir.**

Croow MultiReader; eski, silik, kirli, taranmış belgeleri (daktilo yazısı, yazışmalar, açığa çıkarılmış arşiv sayfaları, adli incelemeye konu sayfalar) **okumak, temizlemek ve anlamlandırmak** için bir masaüstü uygulamasıdır (Windows · macOS · Linux). Hazır bir OCR kütüphanesi kullanmaz: harfleri **belgenin kendisinden öğrenir**, bu öğrenmeyi sen yönlendirirsin.

> **Önemli:** Croow bir okuma yardımıdır, delil değildir. Çıktısı tahmindir; kritik kullanımda orijinal belgeyle karşılaştır. Orijinal dosyaların hiçbirine dokunulmaz.

---

## İçindekiler
1. [Ne işe yarar](#ne-işe-yarar) · 2. [Nasıl çalışır](#nasıl-çalışır) · 3. [Öğrenme neden önemli](#öğrenme-neden-önemli) · 4. [İndirme ve kurulum](#i̇ndirme-ve-kurulum) · 5. [Hızlı başlangıç](#hızlı-başlangıç) · 6. [İşlev rehberi](#i̇şlev-rehberi) · 7. [Kısayollar](#kısayollar) · 8. [Veriler nerede saklanır](#veriler-nerede-saklanır) · 9. [Croow ne öğrenir](#croow-ne-öğrenir) · 10. [Okuma testi](#okuma-testi) · 11. [Kaynaktan çalıştırma](#kaynaktan-çalıştırma) · 12. [Katkı ve iletişim](#fikirlere-açığız--i̇letişim) · 13. [Lisans](#lisans)

---

## Ne işe yarar

| Amaç | Nasıl |
|---|---|
| Resimdeki ve PDF'teki yazıyı okumak | Harf paleti + belgenin kendi harfleri, olasılıkla; cümle bağlamıyla düzeltme |
| Kirli / kalınlaşmış / silik harfleri temizlemek | **CriCroow7**: leke azaltma, kopuk çizgileri tamamlama, inceltme (netleştirme) |
| Okunamayan kelimeyi çözmek | **Kelime çözücü**: harf sayısı, bildiğin harfler ve sözlükle aday kelimeler |
| Programı kendi belgene uyarlamak | Harf, kelime, kutu, leke, çizgi, köprü öğretmek; her düzeltmen kaydedilir |
| Resimleri kayıpsız saklamak | **CRW7** formatı, detaylandırma ×2/×4/…, detaylı CRW |

## Nasıl çalışır

1. **Satır ve harf kutuları:** Sayfanın eğimi düzeltilir, yazı satırları ve harf adımı (daktilo ızgarası) bulunur, her harf bir *kutuya* ayrılır. Üstü çizili satırlar ve tarama kenarı ayrıca ele alınır.
2. **Harf deposu:** Her harf için belgeden gerçek örnekler (*gerçek kök*), silik *sanal* kopyaları, ana hattı (iskeleti), genişliği, kirlilik seviyesine göre şablonları (*nizami / orta kirli / kirli*) ve ortak yolu tutulur.
3. **Olasılık:** Bir kutu depodaki harflerle karşılaştırılır; her harfe bir olasılık verilir (panelde en olası harf ve ikinci aday, yüzdesiyle gösterilir).
4. **Bağlam:** Kelime sözlüğü ve komşu kelimeler olasılıkları düzeltir ("bu harf bu kelimeye gelir mi?").
5. **Sen:** Doğruysa "Doğru", yanlışsa doğrusunu yazarsın; Croow örnek olarak kaydeder. Aşağıdaki her işlev bu döngüye hizmet eder.

## Öğrenme neden önemli

Croow, önceden eğitilmiş dev bir model değildir; **sana ve belgene göre öğrenen** bir sistemdir. Hiç öğretilmemiş bir belgede zayıftır. Her *Doğru*, her düzeltme, her fırça darbesi, her etiket ona örnek olur ve **bir sonraki sayfalara taşınır**. Ne kadar çok ve ne kadar temiz öğretirsen o kadar iyi okur.

- Önce birkaç sayfa/birkaç paragraf öğret; sonra aynı yazı tipindeki yeni sayfaları dene.
- Yanlış öğretmek de öğretir: emin olmadığın şeyi geçmek (`Ctrl+→`) onu yanlış öğretmekten iyidir. Her öğretme **Ctrl+Z ile geri alınabilir**.
- Doğruluk, öğrettiğin belgeye ve öğretme miktarına bağlıdır; bu yüzden hazır bir oran vermiyoruz. Kendi belgende ölçmek için `okuma_testi.py` var (bkz. [Okuma testi](#okuma-testi)).

## İndirme ve kurulum

[Releases](https://github.com/AlperPe/Croow-MultiReader/releases/latest) sayfasından indir:

| Sistem | Dosya |
|---|---|
| Windows (x64) | `CroowMultiReader-Setup-x64.exe` — kurulum sihirbazı, başlat menüsü, `.crw` ilişkilendirme |
| macOS (Apple Silicon) | `CroowMultiReader-macos-arm64.dmg` |
| macOS (Intel) | `CroowMultiReader-macos-intel.dmg` |
| Linux (x86_64) | `CroowMultiReader-x86_64.AppImage` |
| Linux (ARM64) | `CroowMultiReader-aarch64.AppImage` |

- **Windows:** İmzasız olduğu için SmartScreen uyarı verebilir: "Ek bilgi" → "Yine de çalıştır".
- **macOS:** DMG'yi aç, uygulamayı Uygulamalar'a sürükle; ilk açılışta **sağ tık → Aç** (ya da `xattr -dr com.apple.quarantine "/Applications/Croow MultiReader.app"`).
- **Linux:** `chmod +x CroowMultiReader-*.AppImage && ./CroowMultiReader-x86_64.AppImage`. Menüye eklemek için bir kez `--kur` ile çalıştır.
- **Arch Linux (kaynaktan):** `sudo pacman -S tk python-pillow python-numpy poppler` (PDF için), sonra [Kaynaktan çalıştırma](#kaynaktan-çalıştırma).

## Hızlı başlangıç

1. **Aç…** ile bir resim ya da PDF aç (birden çok dosya seçebilirsin; her biri kendi sekmesinde). PDF'ler sayfa **resmi** olarak açılır.
2. (İlk kullanım) **Araçlar → Harf paletini alfabeden öğret** — genel bir başlangıç paleti.
3. Soldaki listeden **Harf göster ve öğret**'i seç; Croow harf kutularını çizer.
4. Bir harfe **tıkla**. Croow sandığını söyler. Doğruysa **Doğru** (ya da Enter), değilse doğrusunu yazıp **Düzelt ve öğret**.
5. Yan paneldeki **Kelime çözücü**'de kelimeyi doğrusuyla yaz (`Tab` Croow'un tahminini düşürür, `Enter` öğretir).
6. Temizlik gerekiyorsa **CriCroow7** adımlarını sırayla çalıştır (Leke azalt → Tamamla → Netleştir); beğenmediğini **Ctrl+Z** ile geri al.
7. Sayfayı baştan okutmak için panelde **Sayfayı oku (baştan)** ya da **CriCroow7 · Anlamlandır**.

## İşlev rehberi

### Dosyalar ve görünüm
- **Sekmeler:** Her dosya kendi sekmesinde, kendi görünümüyle açılır; bütün sekmeler **aynı harf deposunu** paylaşır (biri öğrenince hepsi öğrenir). `Ctrl+W` kapatır.
- **Yakınlaştırma:** `Ctrl+tekerlek`, `+`/`−`, *Sığdır*, *%100*; orta ya da sağ tuşla sürükleyerek kaydır. Büyük sayfalarda yalnızca görünen kısım çizilir.
- **PDF:** Sayfalar 300 DPI resim olarak açılır (3 sayfaya kadar hepsi, fazlası için sayfa aralığı sorulur). Düz metne çevirmek için **Araçlar → PDF'i metne çevir…**.
- **Dosya penceresi:** Croow'un kendi dosya seçicisi (Yukarı / Ev / İndirilenler düğmeleri, yol satırı, tür süzgeci; tıklama yalnızca seçer, çift tık / Enter açar).
- **Kaydet:** PNG, WebP, CRW7, **Detaylı CRW**; metni `.txt` olarak.

### Harf göster ve öğret
Croow harf kutularını bulur; bir harfe tıklayınca panel açılır.
- **Mavi çerçeve = Croow'un baktığı kutu**; panelde büyütülmüş görüntüsü görünür. Kenarını/köşesini panelde ya da resimde sürükleyerek **daralt**, içinden sürükleyerek taşı. *Kutuyu mürekkebe sıkıştır* kutuyu harfe oturtur. **Esnek kutu (8 noktalı çerçeve)** seçeneği dikdörtgen yerine harfi saran çokgen kullanır; çerçevenin dışındaki leke onayda silinir.
- **Doğru / Düzelt ve öğret:** Harf, kutu konumu ve kirlilik seviyesiyle birlikte öğrenilir. Birden çok harf içeren genişletilmiş kutuya içeriğini yazarsan (örn. `19`) kutu o kadar harfe bölünüp her biri öğretilir.
- **Onaylayınca o harfi nizami (temiz) yap:** Onayladığın harf o konumda temiz haline getirilir (harfin ortak yolu / yazı tipi referansı esnetilerek). Harf bozulacaksa *koruyucu* dokunmaz ve nedenini yazar. `Ctrl+Z` geri alır.
- **Kutu düzeltme:** `Shift+sürükle` yeni kutu, `Delete` sil, *Sağdakiyle birleştir*, *İkiye böl*, ok tuşları 1 piksel (`Shift+ok` sağ/alt kenarı büyütür). Düzeltmelerin tutarlıysa kutu kayması **öğrenilir** ve sonraki sayfalara otomatik uygulanır.
- **Varyasyonlar:** Bir harfin kirli → orta → nizami şablonları yan yana görünür; öğretirken seviyeyi sen seçebilirsin. *Yazı ailesi* alanıyla farklı yazı tipleri ayrı tutulur.

### Kelime çözücü (yan panel)
Kelimenin harf sayısını bulur, emin olduğu harfleri konumlarıyla gösterir (`O O M _ I _ _ I _ _`), yuvalara yazdıkça sözlüğü süzüp adayları sıralar.
- `Tab`: Croow'un tahminini boş yuvalara yazar · `Enter`: öğretir · `←/→`: yuvalar arası · `Backspace`: geri sil.
- `Ctrl+→` / `Ctrl+←`: öğretmeden sonraki / önceki kelimeye geç (anlamadığın kelimeyi atla). Seçilen kelimeye görünüm kayar.
- **Kelime doğru**, **Seçili adayı öğret**, **Yazdığımı öğret**. Doğru yazma modu açık kalır: imleç tıklamadan yuvada bekler.
- **Sayfayı oku (baştan):** öğrenilenlerle sayfayı yeniden okur (kelime öğretirken otomatik okunmaz).

### Üç aşamalı öğrenme
Harfleri **üst üste 10 kez** doğru bildiğinde sıra **kelimelere**, kelimeleri de 10 kez üst üste doğru bildiğinde **bütün metin**'e geçilir: Croow sayfayı okur, sen yanlış satırları düzeltirsin, düzeltilmiş metinden sayfa öğrenilir. Böylece güveni ölçülü şekilde artar.

### Diğer öğretme yolları
| İşlev | Ne yapar |
|---|---|
| **Bu sayfadan harf öğret (doğru metniyle)** | Sayfa resmi + o sayfanın doğru metni → depo (hizalama satırları kendisi eşler) |
| **Bu budur…** | Bölge seç → harf ya da kelimeyi yaz → o bölgeden öğrenilir (seviye seçilebilir) |
| **Eşleştir** | Aynı harfe ait kutuları (farklı sekmelerden de) seç, harfi yaz; bilmiyorsan Croow bir "bilinmeyen simge" atar, sonra adını verirsin |
| **Cümle bağlamı öğret** | Düz metin (.txt) dosyalarından kelime sözlüğü ve komşuluklar; boşluk doldurmanın gücü sözlüğe bağlıdır |
| **Harf paletini alfabeden / metinli PDF'lerden öğret** | Genel başlangıç paleti |

### CriCroow7 — temizleme ve anlamlandırma adımları
Her adım ayrı bir düğmedir; orijinal dosya değişmez, **Baştan al (orijinale dön)** her zaman vardır.

| Adım | Amaç |
|---|---|
| **Leke azalt** | Harf kutularının dışındaki izleri, tozu, altı çizili çizgileri azaltır; **elle sildiklerinden öğrenilen leke kuralı** ve siyah leke yumuşatma (referans harfe benzerlik) burada çalışır. Sıkı ve güvenli. |
| **Leke azalt, riskli** | Aynı adım, kuralı esneterek: komşu yazıya yakın, biraz büyük izleri de siler. |
| **Seçili bölgenin içini / dışını riskli temizle** | Yazı mı leke mi olduğunu anlar; yazı yoksa hepsini siler, varsa yazıyı korur. Esnek çerçeveyle çokgenin içinde çalışır. |
| **Tamamla (kopuk çizgi)** | Kopuk çizgileri, çizgi düz geliyorsa ve karşıda mürekkep varsa köprüler. Elle çizdiğin köprülerden boşluk uzunluğunu öğrenir. *Riskli* sürümü daha uzun boşlukları kapatır. |
| **Netleştir (incelt)** | Kalınlaşmış harfleri genel inceltmeyle inceltir. |
| **Netleştir (harfin nizami hâline göre)** | Harfi tanır, kirlilik seviyesini ölçer, ortak yoluna göre inceltir; harf bozulursa o kutunun adımı geri alınır. |
| **Netleştirme zinciri** | Önce genel inceltme ×10, sonra harfin yoluyla ×3 (uzun sürer). |
| **Anlamlandır (oku + cümle bağlamı)** | Harf olasılıkları + sözlük bağlamıyla okur. |
| **Değişiklik haritası / Kaydet** | Neyin değiştiğini gösterir; resim + harita + rapor kaydeder. Rapora "elle düzenleme" adımları da girer. |

`Ctrl+Z`, son CriCroow7 adımını (son 4 adım), son fırça darbesini ve son nizami dönüşümü, hangisi en sonsa onu geri alır.

### Elle düzenleme: Sil / Çiz fırçası
Araç çubuğunda **Sil** (mürekkebi kâğıt rengine boyar) ve **Çiz** (mürekkep ekler). **Boyut, Sertlik, Saydamlık** ayarlanır; fare ucunda fırça halkası görünür.
- **Küçük fırça** (yazı içi): silinen izlerin şekli, boyutu, doluluğu ve konumu **leke örneği** olur. Silmeden önce Croow'un onu neye benzettiğini söyler; sildikçe o şekle benzeyenlerin harf benzerliği düşer.
- **Büyük fırça** (çapı satır boyunun ≥2 katı): **bölge temizliği** öğrenilir (yoğun, harfe benzemeyen alanlar).
- **Çiz**: eski mürekkebe bağlanan çizgiler **köprü** örneği olur.

### Bölge seçimi ve etiketle öğretme
- **Bölge seç:** sürükleyerek dikdörtgen çiz; CriCroow7 adımları yalnızca orada çalışır. **Mürekkebe yapıştır (8 nokta)** bölgeyi izi saran 8 noktalı çerçeveye çevirir. Noktaları sürükle; çerçevenin **kenarına sağ tıkla** → yeni tutma noktası; **noktaya sağ tıkla** → sil.
- **`Ctrl+sol tık`: hızlı seçim.** Tıkladığın iz (birleşik parça) 8 noktalı çerçeveyle seçilir ve "bu ne?" menüsü açılır. `Ctrl+Shift+tık` seçime ekler.
- **Seçileni öğret ▾:** Leke · Leke ve sil · Metin (yazı) · Alt çizgi · Alt çizgi ve sil · Karartma / sansür · Damga / mühür · İmza / el yazısı · **Diğer…** (kendi kategorini aç: ad yaz; benzeyenler mor çerçevede olasılıkla görünür; işaretle / sil / koru).
  - *Leke*, *Alt çizgi* silme kuralına; *Metin, Karartma, Damga, İmza* **koruma** listesine girer (benzeyenlere hiçbir silme adımı dokunmaz).
  - "… ve sil" sonrası çerçeve kaybolur.

### İzleyerek öğrenme ve öneriler
Croow varsayılan olarak **yalnızca izler**: yaptığın her silme, çizme, etiket ve düzeltme kaydedilir; araç çubuğunda özet görünür ("Croow izliyor · leke 6 · bölge 2 · köprü 3 · koruma 7 …"). İstersen **Önerileri göster**'i aç: öğrendiğin şekle çok benzeyen izler turuncu (üstünde benzerlik %) işaretlenir. **Önerileri uygula** onları siler; yanlış öneriye `Ctrl+tık` → **✗ Bu öneri YANLIŞ** (o şekil korunur, bir daha önerilmez). Öneriler sıkı çalışır: en az 5 silinmiş iz ve %60+ benzerlik gerekir.

### CRW formatı
**CRW7** görüntüyü kayıpsız saklar (palet motorun renk hafızasından kurulur). **Detaylandır** ×2, ×4, ×8… büyütür (orijinalin ötesindeki pikseller motorun tahminidir); **Motorla yeniden çiz** yarı boyuttan yeniden üretir; **Detaylı CRW** orijinali, uygulanan adımları ve piksel yollarını tek dosyada taşır.

## Dil (Türkçe / English)

Arayüz dili **Yardım → Dil / Language** menüsünden seçilir (yeniden başlatınca geçerli olur). İlk açılışta sistem diline bakılır; Türkçe değilse İngilizce açılır. `CROOW_DIL=tr` ya da `CROOW_DIL=en` ortam değişkeniyle de zorlanabilir.

## Kısayollar

| Kısayol | İşlev |
|---|---|
| `Ctrl+O` / `Ctrl+W` | Dosya aç / sekmeyi kapat |
| `Ctrl+Z` | Son işlemi geri al (fırça darbesi, nizami dönüşüm, CriCroow7 adımı, etiket) |
| `Ctrl+tekerlek`, `Ctrl++`, `Ctrl+−`, `Ctrl+0` | Yakınlaştır / uzaklaştır / sığdır |
| Orta ya da sağ tuşla sürükle | Görüntüyü kaydır |
| **Sağ tık** (çerçeve kenarında / noktada) | Esnek çerçevede nokta aç / sil |
| **`Ctrl+sol tık`** | Hızlı seçim + "bu ne?" menüsü; `Ctrl+Shift+tık` seçime ekler |
| `Shift+sürükle` (Harf göster) | Yeni harf kutusu çiz |
| `Delete` / `Backspace` | Seçili harf kutusunu sil |
| Ok tuşları / `Shift+ok` | Kutuyu 1 piksel taşı / sağ-alt kenarı büyüt |
| `Enter` (harf kutusunda) | Doğru ya da Düzelt ve öğret |
| `Tab` (kelime yuvalarında) | Croow'un tahminini boş yuvalara yaz |
| `Enter` (kelime yuvalarında) | Yazdığını öğret (hiç yazılmadıysa: yalnızca sözlükte bir kelimeyse Croow'un okuması doğru sayılır) |
| `←` `→` (yuvalarda), `Backspace` | Yuvalar arası / geri sil |
| `Ctrl+→` / `Ctrl+←` | Sonraki / önceki kelimeye **öğretmeden** geç |
| Dosya penceresi: `Alt+↑`, `Backspace`, `Esc` | Üst klasör / üst klasör / kapat |
| Metinde: `Ctrl+C`, `Ctrl+A` | Kopyala / tümünü seç |

## Veriler nerede saklanır

Croow her şeyi **kendi bilgisayarında** tutar; hiçbir veri bir yere gönderilmez. Varsayılan klasör **`~/.croow/`** (Windows: `C:\Users\<ad>\.croow\`). `CROOW_VERI` ortam değişkeniyle başka yere taşınabilir (örn. her proje için ayrı depo).

| Dosya | İçerik |
|---|---|
| `harf_koklari_v6.crw` | **Genel harf paleti** (yazı tiplerinden / metinli PDF'lerden) |
| `belge_harf.crw` | **Gerçek harf kökleri**: senin belgelerinden öğrenilen harf örnekleri |
| `belge_harf_sanal.crw` | **Sanal (silik) kopyalar**: gerçek harflerden üretilen silik sürümler |
| `belge_kelime.crw` | Kelime sözlüğü ve komşuluk sayıları, harf kalıpları, ana hatlar, genişlikler, **varyasyon şablonları**, **harf yolları**, kutu düzeltmeleri, **elle düzenleme örnekleri** (leke, bölge, köprü, çizgi, koruma, özel kategoriler) |
| `yazi_yollari.crwm` | Yazıdan öğrenilmiş piksel yolları (isteğe bağlı) |
| `sayfalar/` | PDF'lerden çizilen sayfa resimleri (PNG) |
| `universal_roots.crwm` | Croow renk hafızası (isteğe bağlı; yoksa boş) — uygulamanın yanına da konabilir |

- **Yedekleme:** `~/.croow/` klasörünü kopyala. **Sıfırdan başlama:** klasörü yeniden adlandır/sil. Eğitilmiş hafıza ve palet dosyaları depoya girmez (`.gitignore`).
- Orijinal resimler/PDF'ler **değiştirilmez**. Fırça ve temizleme ekrandaki çalışma kopyasındadır; kaydetmediğin sürece diske yazılmaz (öğrenilenler ise kaydedilir).

## Croow ne öğrenir

| Sen ne yaparsın | Croow neyi kaydeder | Nerede işe yarar |
|---|---|---|
| Harfi onaylar / düzeltirsin | Harf örneği, sanal kopya, kalıp, ana hat, genişlik, kirlilik seviyesi, ortak yol | Okuma olasılıkları, nizami dönüşüm |
| Kutuyu düzeltirsin | Kutu kayması (satır boyuna oranla) | Sonraki sayfalarda kutular otomatik oturur |
| Kelimeyi öğretirsin | Kelime ve komşuluk sayıları, her harfin kutusu | Boşluk doldurma, bağlam düzeltmesi |
| Fırçayla **silersin** | İzin şekli, boyutu, doluluğu, konumu (+ 24×24 şablon) | **Leke azalt** (öğrenilen kural), öneriler, harf benzerliğinin düşürülmesi |
| **Büyük fırçayla** temizlersin | Bölgenin yoğunluğu, büyük iz payı, harfe benzeyen payı | **Riskli** leke azalt / bölge temizliği |
| **Çizersin** | Köprülenen boşluğun uzunluğu | **Tamamla** |
| **Seçileni etiketlersin** | Leke / çizgi → silme kuralı; metin, karartma, damga, imza → koruma şablonu; özel kategori → şablon + eylem | Silme adımları korunanlara dokunmaz; mor olasılık işaretleri |
| Öneriyi **yanlış** dersin | O şekil koruma listesine eklenir | Bir daha önerilmez |

Öğrenme güvenli tasarlandı: kural çıkarmak için en az örnek sayısı aranır (leke ≥3, bölge ≥2, öneri ≥5), her şey `Ctrl+Z` ile geri alınır.

## Okuma testi

`uygulama/okuma_testi.py`, **öğretilen satırlar ile sınanan satırları ayırarak** adil ölçüm yapar:

```bash
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt              # ilk yarıdan öğret, kalanı oku
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt --egit 0.3   # ilk %30'dan öğret
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt --egit 0     # hiç öğretme (genel palet gerekir)
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt --capraz     # çift/tek satırlarla iki yönlü
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt --metin klasor/   # bağlam için .txt klasörü
python uygulama/okuma_testi.py sayfa.png dogru_metin.txt --goster     # satır satır doğru / okunan
```

`dogru_metin.txt`: sayfadaki satırlar, her satır bir satır, sayfa sırasıyla. Çıktı: karakter ve kelime doğruluğu (düzenleme mesafesi), bağlamsız ve bağlamlı. Geçici depo kullanır, verini bozmaz.

## Kaynaktan çalıştırma

```bash
pip install pillow numpy pypdfium2
python uygulama/croow_reader.py          # Croow MultiReader (tkinter gerekir)
python egitim/croow_egit.py <foto_klasoru> --hafiza universal_roots.crwm   # renk hafızası eğitimi (isteğe bağlı)
```

| Klasör | İçerik |
|---|---|
| `uygulama/` | MultiReader: arayüz (`croow_reader.py`, `croow_gorunum.py`, `croow_dosya.py`), harf deposu ve okuma (`belge_harf.py`, `crw_harf.py`), CriCroow7 (`cricroow.py`), PDF (`crw_pdf.py`, `pdf_motor.py`), okuma testi |
| `motor/` | CRW kodlayıcı/açıcı (`crw_motor.py`), renk hafızası (`roots_memory.py`), piksel yolları (`paths_memory.py`) |
| `egitim/` | Renk hafızası eğitim betiği |
| `paketleme/` | Simgeler, PyInstaller tarifi, Windows kurulum sihirbazı, Linux AppImage dosyaları |
| `.github/workflows/` | Her `v*` etiketinde Windows, macOS ve Linux kurulum dosyalarını derler |

## Fikirlere açığız · İletişim

Croow genç ve **öğrenerek gelişen** bir proje; en çok **kullananlardan** öğreniyoruz. Okuma doğruluğunu artıracak fikirler, yanlış okunan örnekler, zor belgeler, kullanım kolaylığı önerileri, hata raporları ve katkılar çok değerli. İstediğin gibi yaz:

**📧 pektalper@croowsearch.com**

Hata ve öneriler için GitHub'da *Issues* de açabilirsin. Bir hata raporunda sayfanın (paylaşabiliyorsan) küçük bir kırpığını, ne yaptığını ve alt çubuktaki mesajı eklemek çok yardımcı olur.

## Lisans

Copyright (C) 2026 Alper Pektas

Bu program **GNU Affero Genel Kamu Lisansı sürüm 3 (AGPLv3)** ile lisanslıdır (`LICENSE`). Ek koşullar `NOTICE` dosyasındadır:

- Yazar bildirimi ("Croow — Alper Pektas tarafından geliştirilmiştir.") kaynakta, her kopyada, belgelerde ve kullanıcı arayüzünde korunmalıdır.
- Değiştirilmiş sürümler orijinal Croow gibi sunulamaz.
- Bu programı ya da değiştirilmiş bir sürümünü ağ hizmeti olarak sunan herkes, kullanıcılarına tam kaynak kodunu sunmak zorundadır (AGPLv3 Madde 13).
