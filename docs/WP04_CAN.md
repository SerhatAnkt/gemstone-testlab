# WP-04 — vcan fixture ve CAN sözleşmesi

Bu belge WP-04 tesliminin kaydıdır. Güncel çalıştırıcı WP-05'te 36 vakalık CAN
matrisine genişletildi; alıcı ve argüman testleri için [WP05_CAN_MATRIX.md](WP05_CAN_MATRIX.md)
dosyasını okuyun. Aşağıdaki 6 test ve 28 host sayıları WP-04'e aittir.

Kabul ölçütü: C, C++ ve Python CAN göndericilerinin ilk çerçeveleri bağımsız
referansla doğrulanır. Bu teslim ilk mesajın ardından kontrollü SIGINT, END
çerçevesi, normal çıkış ve kaynak sahipliğini de sınar.

## Doğrulanan sonuç

28 ayrıcalıksız host kontrolü ve ayrı Linux konuğunda 6 gerçek vcan testi geçti.
pytest ve üç hedef **UID 1000** ile çalıştı. Yalnızca arayüz yönetim komutları
sudo ile yükseltildi. Altı sahipli arayüz kaldırıldı; kalan `gtl` arayüzü yoktu.
Bu iş için bir Gemstone kartı kullanılmadı.

| Gönderici | İlk CAN ID | Veri uzunluğu | Verinin hex gösterimi |
| --- | --- | --- | --- |
| C | `0x123` | 8 | `4d53475f30303000` |
| C++ | `0x123` | 8 | `4d53475f30303000` |
| Python | `0x123` | 7 | `4d53475f303030` |

Üçü de SIGINT sonrasında ID `0x124`, uzunluk 3, veri `454e44` (`END`) üretti ve
0 ile kapandı. C/C++ sonundaki NUL korunur; Python için sahte bir NUL eklenmez.
Bu başlangıç davranışı `can_examples_v1` sözleşmesidir.

## Bileşenler

| Dosya | Görev |
| --- | --- |
| `tests/testlab/contracts.py` | Değerlendirilecek kimlik/veri beklentileri ve klasik Linux CAN çözümü |
| `tests/testlab/can.py` | Vcan sahipliği, kimlik kontrolü ve bağımsız ham CAN soketi |
| `tests/conftest.py` | pytest seçenekleri ve her çalışmaya ait kanıt kökü |
| `tests/can/conftest.py` | Normal kullanıcı önkoşulu, program derleme/seçimi ve vcan fixture |
| `tests/can/test_sender.py` | Üç gönderici ve üç kaynak yaşam döngüsü testi |
| `tests/host/test_can_contracts.py` | Donanım/yetki istemeyen altı sözleşme kontrolü |
| `tests/scripts/run-can-tests.sh` | Modülü hazırlayıp pytest'i normal kullanıcıyla başlatma |
| `tools/run_can_suite_vm.py` | Aynı pytest testlerini ayrı Linux konuğunda çalıştırma |

## Vcan yaşam döngüsü

1. `gtl` ve 10 rastgele hex karakterden 13 karakterlik bir ad üretilir.
2. Mevcut arayüzlerin JSON kaydı okunur; ad doluysa mevcut kaynak benimsenmez.
3. Vcan oluşturulur; `ifindex`, `info_kind=vcan` ve benzersiz `ifalias` kaydedilir.
4. Arayüz UP yapılır ve durum doğrulanır.
5. Bağımsız referans soketi **göndericiden önce** bağlanır.
6. İlk çerçeve doğrulanır; SIGINT sonrası END ve süreç çıkışı doğrulanır.
7. Süreç ve referans soketi kapanır. Sonra fixture yalnızca kendi kimliği hâlâ
   eşleşen arayüzü siler ve silindiğini tekrar sorgular.

Sahiplik değişmişse silme reddedilir. Aynı adın başka bir arayüze verilmesi,
index/alias değişmesi veya kaynağın yeniden adlandırılması sessizce başarılı
temizlik sayılmaz. Vcan modülü kaldırılmaz; başka arayüzler değiştirilmez.

Üç ek entegrasyon kontrolü:

- Senaryo kontrollü istisna üretse de kendi arayüzü silinir.
- İkinci lease mevcut adı kullanmaya çalışınca reddedilir; ilk sahibin arayüzü kalır.
- Sahiplik alias'ı değişince silme reddedilir. Test, kendi bilinçli değişikliğini
  geri aldıktan sonra kaynağını temizler. İlk reddin hata kaydı korunur.

Son testteki kontrollü `cleanup_error`, testin yakalamayı beklediği durumdur;
kanıt gizlenmez veya normal kapanış diye değiştirilmez.

## Sözleşmenin sınırları

Referans uç uygulamanın alıcısını, gönderici sınıfını veya çıktı metnini kullanmaz.
Linux SocketCAN'dan alınan ham frame'i çözer; CAN ID, uzunluk ve veri ayrı doğrulanır.
Standart 11 bit klasik veri çerçevesi beklenir. EFF/RTR/ERR bitleri maskelenerek
gizlenmez; yanlış çerçeve boyutu ve sekizden büyük veri uzunluğu reddedilir.

WP-04 ilk normal ve kapanış mesajını kapsar. Alıcı matrisi, uzun mesaj akışları,
hatalı arayüz parametreleri ve diğer hata senaryoları WP-05'e aittir.
Vcan fiziksel hat, CRC, transceiver, bus-off veya zamanlama ölçümü değildir.
O1/AM67A/R5 emülasyonu yapılmaz; bu testler Linux kullanıcı alanı örneklerinindir.

## Normal Linux üzerinde çalıştırma

Test edilmiş profil Ubuntu 24.04 / Python 3.12'dir. Gerekli sistem araçları:
`build-essential`, `python3-venv`, `iproute2`, `kmod`, `sudo`. Vcan modülü çekirdekle
eşleşmelidir. Kurulumdan sonra normal kullanıcıyla:

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements.txt
TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-can-tests.sh --evidence-root artifacts/can -q
```

Modül önceden hazırsa doğrudan `.venv-testlab/bin/python -m pytest tests/can`
çağrılabilir. pytest root kullanıcıyı reddeder. Fixture'ın `sudo -n ip` çağrılarına
etkileşimsiz yetki gerekir; parola beklenmez. Her ip çağrısı ortak süreç modülüyle
5 saniye sınırındadır. Eksik kernel/yetki/araç test hatasıdır; skip/yeşil sonuç değildir.

pytest bağımlılıkları resmi PyPI SHA-256 özetleriyle kontrol edildi:
`pytest==8.4.2` ve transitif bağımlılıkları `tests/requirements.txt` içinde tam
sürümleriyle yer alır. Bu kilit Python 3.12 profili içindir. Proje kaynaklarını
derlemek için geniş Gemstone SDK/Qt bağımlılıkları kurulmaz.

## Kısıtlı host için ayrı Linux konuğu

WP-01'deki QEMU/kernel kökünü [VM_REPRODUCTION.md](VM_REPRODUCTION.md) ile hazırlayın.
Ubuntu 24.04 uyumlu host üzerinde sistem Python 3.12, sudo/PAM ve iproute2 gerekir.
Seçilmiş wheel dosyalarını hazırlayıp çalıştırın:

```sh
.venv-testlab/bin/python -m pip download --require-hashes -r tests/requirements.txt --only-binary=:all: --dest .vm-wheels
python3 tools/run_can_suite_vm.py --guest-root .vm-root --wheels .vm-wheels --output artifacts/can-guest
```

İsteğe bağlı `--source-root /tam/yol/examples` mevcut kaynak ağacını seçer.
Araç checkout/reset yapmaz. Native C/C++ göndericileri host Makefile'larıyla
derlenir; kaynak ve binary özetleri doğrulanarak aynı x86 mimarili konuğa taşınır.
Python göndericisi seçilmiş kaynaklardan çalışır. Bu bir ARM64 çapraz derleme değildir.

Konuğa sistem Python/stdlib, gerekli dinamik kitaplıklar ve doğrulanmış pytest
wheelleri eklenir. `guest-runtime.json` her taşınan dosyanın kaynağını/özetini kaydeder.
Host konfigürasyonu veya kullanıcı bilgileri kopyalanmaz. Konukta üretilmiş tester
hesabı, PAM ayarı ve yalnızca `/bin/ip` için sudo politikası bulunur. Root başlangıç
adımı modülleri yükler; pytest alt süreci tüm UID/GID'lerini 1000 yapar.

Konuk için NIC, disk veya KVM eklenmez. Testler konuğun gerçek Linux çekirdeği ve
vcan modülünde çalışır. Kanıt dosyaları sıkıştırılmış ve SHA-256 kontrollü olarak
seri konsoldan alınır. VM kapandıktan sonra host'ta `guest-artifacts/` altında
açılır; ham konuk yolları JSON içinde korunur. Büyük initramfs/OS dosyaları proje
ZIP'ine eklenmez. Aynı host kitaplıklarının başka sürümleri yeni özetler üretebilir.

## Kanıtlar

- `pytest.log` ve `junit.xml`: gerçek test sayıları ve sonuçları.
- `case.json`: varyant, beklenen/gözlenen frame, runner UID ve hedefin dört UID alanı.
- `lease.json`: ad/index/alias, ip komutları, sahiplik ve silme sonucu.
- `process.json`: hedef ve ip süreçlerinin sinyal/çıkış/temizlik kaydı.
- VM `run.json`: bağlam, UID, sonuçlar ve host derleme raporu.

JUnit'i pytest üretir. Ortak hata tekrar üretim paketi ve tam rapor arayüzü WP-07
kapsamındadır. GitHub Actions dosyası güncellendi; gerçek GitHub-hosted run hâlâ yapılmadı.

Dayanak: [Linux SocketCAN belgeleri](https://docs.kernel.org/networking/can.html).
Paketin başarı iddiaları belgede anlatılan kabiliyetlere değil, kaydedilmiş gerçek çalışmalara dayanır.
