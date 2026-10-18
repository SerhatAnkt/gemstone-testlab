# WP-02 — hedef listesi ve derleme yöneticisi

Kabul ölçütü: altı C/C++ hedef ayrı host dizinlerinde derlenir; her komut ve çıktı
kaydedilir. Bu kabul ölçütü yerel Linux x86_64 ortamında sağlandı.

## Hedefler

| Kimlik | Kaynak dizini | Binary |
| --- | --- | --- |
| `can.c.sender` | `canbus/c/sender` | `canbus-sender` |
| `can.c.receiver` | `canbus/c/receiver` | `canbus-receiver` |
| `can.cpp.sender` | `canbus/cpp/sender` | `canbus-sender` |
| `can.cpp.receiver` | `canbus/cpp/receiver` | `canbus-receiver` |
| `serial.c` | `serial/c` | `serial` |
| `serial.cpp` | `serial/cpp` | `serial` |

Aynı isimli binary'ler hedef kimliği ve run kimliğiyle farklı dizinlere yazılır.
Python uygulamaları derleme hedefi değildir; sonraki I/O senaryolarında seçilen
Python yorumlayıcısıyla çağrılacaktır.

## Çalıştırma

```sh
python3 -m tests.testlab build
python3 -m tests.testlab build --target can.cpp.sender --target serial.cpp
python3 -m tests.testlab build --source-root /tam/yol/examples --output-root artifacts/my-build
python3 -m tests.testlab build --cc gcc --cxx g++ --timeout 60
```

`--source-root` verilmezse:

1. TestLab examples deposunun köküne entegre edilmişse bu çalışma ağacı kullanılır.
2. Bu bağımsız pakette `upstream/examples` çalışma ağacı kullanılır.

Derleme sırasında indirme, checkout veya kaynak geri alma yapılmaz. Değiştirilmiş
kaynaklar da derlenir. Git deposu bulunursa commit ve kaynak kökü için dirty
durumu kaydedilir; bulunmazsa commit/dirty `null` olur. Referans commit hiçbir
zaman bulunamayan gerçek Git commit'iymiş gibi gösterilmez.

## Derleme ve kaynak kaydı

Her hedefin kendi Makefile'ı çağrılır. `PROJDIR`, `BUILDDIR`, `CC` veya `CXX`
açıkça aktarılır. Özgün `common.mk` uyarı ayarları korunur. Host profili, miras
alınmış Make/derleme bayrağı değişkenlerini kaldırır; kaldırılan adlar raporda
görünür. Derleyici seçmek için `--cc`/`--cxx` kullanılmalıdır. Bunlar shell komutu
değil tek çalıştırılabilir dosya adıdır.

Her run yeni bir dizin kullanır; eski `.o` veya binary tekrar kullanılmaz.
Kaynak ağacında genel `make clean` çalıştırılmaz. Önceki çıktılar silinmez.

`run.json` şunları içerir:

- Seçili hedeflerin kaynak/header/Makefile özetleri ve ortak `.mk` dosyaları.
- Bu girdilerin referans kilitle karşılaştırılması; fark varsa dosya adları.
- Derleme öncesi/sonrası girdi özetleri; derleme sırasında değişiklik başarı sayılmaz.
- Derleyici ve Make sürümleri, argv listesi, cwd, süreler ve çıkış kodları.
- Her binary'nin yolu, boyutu, SHA-256 ve ELF sınıf/makine bilgisi.
- Profil `host`; uygulama çalışma, ARM64 ve kart testlerinin `not_run` durumu.

ELF makinesi host mimarisiyle eşleşmiyorsa host derlemesi başarılı sayılmaz.
Bu ELF kontrolü programın I/O davranışını sınamaz. Şu anda yalnızca `host`
profili vardır; ASan/UBSan ve ARM64 desteği eklenmiş gibi gösterilmez.

Komutlar `commands.jsonl` içinde de sıralı tutulur. Ham stdout/stderr hedefe özel
`build/<hedef>.log` dosyasında birleştirilir. Eksik kaynak veya derleyici durumunda
derleme çağrılmasa bile hedefe özel açıklama dosyası üretilir.

Mevcut upstream Makefile'lar boşluk içeren kaynak/çıktı yollarını düzgün
alıntılamaz. Bu teslimde Makefile'lar değiştirilmedi; proje ve çıktı köklerinde
boşluksuz yollar kullanın. Girdi özeti bilinen hedef dizinleriyle ortak `.mk`
dosyalarını kapsar; tüm sistem başlıklarının veya dış bağımlılıkların kilidi değildir.

## Hata durumları

| Durum | JSON | CLI çıkışı |
| --- | --- | --- |
| Bütün seçili derlemeler ve ELF kontrolleri başarılı | `passed` | 0 |
| Make başarısız, derleme zaman aşımı veya bozuk çıktı | `failed` | 1 |
| Eksik araç/girdi veya derleme sırasında kaynak değişimi | `error` | 2 |
| Geçersiz/tekrarlanan hedef seçimi veya geçersiz yol | CLI kullanım hatası | 2 |

Bir hedef başarısız olduğunda diğer seçili hedefler de değerlendirilir; toplam
sonuç başarılıya dönüştürülmez. Zaman aşımında derleme süreç grubu sonlandırılır.
Uygulama süreçleri için genel yaşam döngüsü altyapısı WP-03'e aittir.

## Regresyon kontrolleri

Python standart kütüphanesi, GCC, Make ve Git gerekir; harici Python paketi gerekmez.

```sh
python3 -m unittest discover -s tests/host -p test_build_manager.py -v
```

Beş kontrol gerçek dosyalar ve gerektiğinde gerçek GCC derlemeleri kullanır:

1. Kaynağın kullanım metnini değiştirir; mtime'ı eski değerde tutar. Yeni binary'nin
   yeni metni ürettiğini ve Git dirty/hash farklarının raporlandığını doğrular.
2. Önce geçerli binary üretir, sonra `#error` ekler. Eski binary mevcutken yeni
   derleme başarısız olmalıdır; aynı çalışmadaki sağlıklı seri hedefi yine derlenir.
3. Olmayan derleyici seçildiğinde `error` ve CLI çıkış kodu 2 bekler.
4. C++ header eksikliğinde Make çağrılmadan hata kaydı bekler.
5. Boş, bilinmeyen ve yinelenen hedef seçimlerinin reddini kontrol eder.

Geçici kopyalar kullanılır; paketlenen upstream dosyalar değişmez. Günlükleri
korumak için `TESTLAB_EVIDENCE_ROOT=artifacts/regression` ortam değişkeni verilebilir.
Bu yardımcı kontroller standart `unittest` kullanır; uygulama senaryoları için
mimari plandaki pytest yaşam döngüsünün yerini alan yeni bir test yöneticisi yoktur.

## Durum

18 Ekim 2026 Türkiye saatiyle altı gerçek derleme ve beş regresyon kontrolü geçti.
WP-01'in GitHub runner kabulü hâlâ açıktır. WP-02'nin ayrıcalıksız derleme kabulü
yerelde tamamlandı; bu sonuç uzak CI'ın çalıştırıldığı iddiası değildir.
