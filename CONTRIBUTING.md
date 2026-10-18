# Katkı kılavuzu

Önce [QUICKSTART.md](QUICKSTART.md) ile host ve seri profillerini çalıştırın.
Proje Apache-2.0 lisanslı bağımsız topluluk katkısıdır; resmî Gemstone ürünü
değildir. Kodda SPDX başlığı, katkıda sorunun somut tetikleyicisi ve gerçek
doğrulama sonucu bulunmalıdır.

## Beş bağımsız uygulama düzeltmesi

[contributions/README.md](contributions/README.md) her düzeltmeyi dosyası,
regresyon seçimi ve İngilizce PR taslağıyla eşler. `series.json` bu eşlemenin
makinece okunabilir kaynağıdır. Her yama kilitli upstream sürümüne **tek başına**
uygulanır; önceki yamanın uygulanmış olması beklenmez.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 02 --output artifacts/pr02-first
```

Kontrol özgün kaynaklarda seçili dört regresyonun `call` fazında başarısız
olduğunu, yalnız 0002 yaması eklenince dördünün geçtiğini doğrular. Başarısız
baseline gerçek pytest kodu 1'i korur; kontrol aracının kodu 0, beklenen
önce/sonra kanıtının tamamlandığı anlamına gelir. Kurulum hatası, skip veya
teardown hatası baseline kanıtı sayılmaz. Kaynak ağacı değişmez.

CAN için normal kullanıcı ve CAN önkoşullarıyla tüm seri:

```sh
.venv-testlab/bin/python tools/check_contributions.py --output artifacts/contributions-first
```

Host yetkisi yoksa hazırlanmış Linux runtime'ı ve wheel diziniyle:

```sh
.venv-testlab/bin/python tools/check_contributions.py --can-backend vm --guest-root /tam/yol/guest-root --wheels /tam/yol/wheels --output artifacts/contributions-vm-first
```

Tek giriş için `--entry 01`…`--entry 05` seçilir; seçenek tekrarlanabilir.
Yalnız seri girişler normal kullanıcı/root ile PTY üzerinden çalışabilir;
CAN testi root ile başlatılmaz. Çıktı yeni dizin olmalıdır. `contributions.json`,
yama check/apply günlükleri ve her girişin baseline/fixed JUnit/JSON dosyaları
kanıttır. Çalışma kopyası başarılı girişte silinir; kanıt ve kaynak snapshot'ı kalır.

## Upstream'e sunma

1. İlgili `contributions/NN-*.md` taslağındaki sorun ve beklenen davranışı okuyun.
2. Hedef dalın güncel sürümünde kusurun hâlâ bulunduğunu yeniden doğrulayın.
   Bulgular yalnız `2619a7584d39203a057abc08ab7c6698dc476868` için kanıtlandı.
3. Kendi examples fork/branch'inizde yalnız ilgili uygulama yamasını uygulayın.
   `git apply --check` başarısızsa zorlamayın; değişikliği güncel dosyaya uyarlayıp
   regresyonu tekrar çalıştırın. TestLab kaynaklarını eski sürüme sıfırlamayın.
4. Küçük uygulama değişikliğini ilgili regresyon testiyle birlikte incelemeye
   hazırlayın. TestLab ayrı depoda tutulacaksa test sürümünü ve komutunu açıkça
   yazın; test altyapısının upstream'de kabul edildiğini varsaymayın.
5. PR'a gerçek önce/sonra raporunu ekleyin. Yerel dosya yolları yerine erişilebilir
   ekler veya gerçek workflow artifact bağlantıları kullanın. Henüz koşulmamış
   bir workflow URL'si veya fiziksel kart sonucu yazmayın.

Bu teslim hiçbir issue/PR göndermedi ve uzak depoyu değiştirmedi. PR taslakları
incelenebilir hazır metindir; yayın kararı ve hedef dal seçimi ayrı adımdır.

## Test altyapısını incelemeye bölme

Beş uygulama yaması ayrı PR olabilir. TestLab altyapısı daha büyük olduğu için
tek seferde upstream'e taşımak yerine şu dosya gruplarıyla incelenebilir:

| Sıra | Değişiklik grubu | İnceleme odağı |
| --- | --- | --- |
| A | Hedefler, derleme, süreç yönetimi ve host regresyonları | Mevcut kaynak, timeout, owned cleanup |
| B | CAN sözleşmesi, fixture ve CAN vakaları | Bağımsız oracle, arayüz sahipliği |
| C | PTY fixture ve seri vakaları | Ham baytlar, iki yön, terminal restorasyonu |
| D | JSON/JUnit, snapshot ve reproduce | Gerçek hata fazı ve kayıtlı girdiler |
| E | Kilitli SDK ve cross-build | AArch64 ELF, host fallback olmaması |
| F | CI, teslim araçları ve kılavuzlar | Tam matris, temiz kurulum, gerçek PR checkout'u |

Bu tablo inceleme önerisidir; uygulanmış altı bağımsız Git commit serisi değildir.
Çalışan bağımlılıklar korunarak hedef deponun yapısına göre commit'ler hazırlanır.

## Test veya kaynak değiştirirken

- `tests/ci-contract.json` zorunlu node'ları içerir. Vaka silmek/yeniden
  adlandırmak bu dosyayla birlikte açıkça incelenir; sözleşme körlemesine yeniden
  üretilerek eksik test saklanmaz.
- Normal çalışma ağacı için `working-tree` kullanılır. Beş uygulama yaması
  kaynaklara entegre edildiğinde `proposed-fixes` aynı yamaları tekrar
  uygulamaya çalışacağından CI seçimi de değiştirilir.
- Kaynak snapshot, harness hash'i, komut ve günlükler korunur. Skip/xfail ile
  zorunlu regresyon gizlenmez. Yeni test davranış değişikliğini bağımsız bir
  beklenen değerle doğrulamalıdır.
- vcan arayüzü benzersiz isim ve sahiplik kimliğiyle yönetilir. Yabancı
  arayüz veya süreç temizliği eklenmez. SDK, wheel, binary ve ham kanıtlar Git'e
  eklenmez; `export_source.py` bunları kaynak dağıtımına da almaz.
- Sonucu host çalışma, x86 vcan/PTY, AArch64 derleme ve fiziksel kart olarak
  doğru adlandırın. O1 donanımına ait doğrulama henüz yoktur.
