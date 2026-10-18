# WP-05 — CAN alıcıları ve hata matrisi

Bu paket mimari plandaki zorunlu CAN matrisini çalıştırır. Gerçek sonuçlar
[RESULTS.md](../RESULTS.md) ve `artifacts/summary.json` içindedir. GitHub runner,
ARM64 ve fiziksel O1 kabulü bu kontrollerle tamamlanmış sayılmaz.

## Matris

| Senaryo | Varyant | pytest sayısı | Kontrol |
| --- | --- | --- | --- |
| CAN-TX-01 + CAN-TX-02 | C/C++/Python | 3 | İlk çerçeve, SIGINT, END ve normal çıkış |
| CAN-RX-01 | C/C++/Python × 0/1/8 bayt | 9 | ID, uzunluk, hex veri ve metin |
| CAN-RX-02 | C/C++/Python | 3 | NUL ve yüksek baytlar kayıpsız okunur |
| CAN-RX-03 | C/C++/Python × exact/prefix | 6 | Yanlış END koşullarında devam, doğru koşulda kapanış |
| CAN-ARG-01 | Altı giriş noktası | 6 | Eksik arayüz: kullanım metni ve çıkış 1 |
| CAN-ARG-02 | Altı giriş noktası | 6 | Olmayan arayüz: açıklayıcı hata ve çıkış 1 |
| Kaynak yaşam döngüsü | Ortak fixture | 3 | İstisna temizliği ve dış kaynağı koruma |
| **Toplam** | | **36** | 33 uygulama vakası ve 3 kaynak vakası |

`can_examples_v1` korunur. C/C++ ilk mesajı `MSG_000\0` (8 bayt), Python ilk
mesajı `MSG_000` (7 bayt) olarak değerlendirilir.

## Bağımsız referans ve hazır olma

`CanPublisher`, standart kütüphanenin ham SocketCAN soketini kullanır; Gemstone
gönderici modüllerini içe aktarmaz. Standart 11 bit kimlik ve 0–8 veri baytı,
16 baytlık Linux `can_frame` yerleşimiyle üretilir.

`ReceiverSession` alıcıyı ortak süreç yöneticisiyle başlatır. stdout raw moddaki
gerçek bir PTY'ye bağlanır; C stdio'nun terminaldeki satır tamponlaması böylece
kullanılabilir. Upstream'e `fflush` eklenmez. stderr ayrı kaydedilir. Bu konsol
PTY'si, seri port aktarım testinin yerine geçmez.

ID `0x321`, veri `GTLREADY` hazırlık çerçevesinin alıcı çıktısında görülmesi
beklenir. Açılış metni tek başına yeterli sayılmaz. Başlangıç/bind yarışı için
0,1 saniye aralık ve native profilde 5 saniye üst sınır vardır. Deneme sayısı
süre bütçesinden hesaplanır; alıcı geç bağlandığında son saniyeler probesiz kalmaz.
İlk çerçeve satırı yazılmaya başlayınca tekrarlar durur; parçalı konsol çıktısı
işlenirken alıcının kuyruğu hazırlık mesajlarıyla doldurulmaz.
Asıl test çerçevesi tekrar gönderilmez. Alıcının dört procfs UID alanı runner'ın
UID'siyle aynı olmalıdır; misafir doğrulamasında bunlar 1000'dir.

## Çıktı ve kapanış sözleşmesi

`parse_receiver_line`, açılış metinlerini ayırır; `Received:` ile başlayan bozuk
çerçeve satırlarını hata sayar. ID'de büyük/küçük hex harf, sıfır dolgu ve veri
arasındaki boşluklar sunum ayrıntısıdır. ID değeri, DLC ve bütün veri baytları
ayrı korunur. DLC yazdırılan hex bayt sayısıyla aynı olmalıdır. ASCII 32–126
aynen, diğer baytlar `.` görünmelidir. EFF/RTR/ERR bayrakları maskelenmez.

İkili veri girdisi `00 01 1F 20 7F 80 FF 41`, metin beklentisi `... ...A` olur.
Sekiz ek host kontrolü çerçeve yerleşimini, 0/1/8 baytı, NUL/yüksek baytları,
DLC/hex/metin bozulmalarını ve tırnaklı veriyi sınar. Bir ek host regresyonu gerçek
süreç/PTY ve simüle edilmiş yayıncıyla geç bağlanma durumunu sınar; SocketCAN
başarısı iddia etmez. Toplam host sayısı 37'dir.

Alıcıların mevcut kapanış koşulu ID `0x124`, en az 3 bayt ve `END` önekidir.
`ENDtail` de geçerli kapanıştır. Her alıcıya önce ID `0x125` ile `END`, ardından
ID `0x124` ile `EN` ve `ENX` verilir. Her birinden sonra farklı bir normal
çerçevenin işlendiği görülmelidir. Yalnızca canlı PID veya bekleme süresi kanıt
sayılmaz. Son olarak `END` ya da `ENDtail`, kapanış metni ve 3 saniye içinde
normal çıkış doğrulanır.

## Çalıştırma

Ubuntu 24.04/Python 3.12 profilinde, normal kullanıcıyla:

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements.txt
python3 tools/prepare_can_fix.py --output build/can-fixed
TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-can-tests.sh --source-root build/can-fixed --evidence-root artifacts/can --junitxml=artifacts/can-junit.xml -q
```

`build-essential`, `iproute2`, `sudo`, `kmod` ve çekirdeğe uygun vcan modülü
gerekir. Yalnızca modül/arayüz işlemleri yükseltilir; pytest ve hedefler normal
kullanıcıda kalır. Eksik önkoşul, atlanmış başarılı test sayılmaz.

Kısıtlı host için kernel/QEMU kökünü [VM_REPRODUCTION.md](VM_REPRODUCTION.md),
kilitli wheelleri [WP04_CAN.md](WP04_CAN.md) ile hazırlayın:

```sh
python3 tools/run_can_suite_vm.py --guest-root .vm-root --wheels .vm-wheels --output artifacts/can-guest
```

Dört native CAN girişi derlenir, iki Python girişi seçilmiş kaynaklardan çalışır.
`--source-root` mevcut değiştirilmiş kaynak ağacını seçebilir; checkout/reset
yapılmaz. PTY için `devpts` konuğun içinde hazırlanır. Toplam QEMU bütçesi 600,
pytest bütçesi 570 saniyedir. Native pytest hazırlık/çerçeve/kapanış sınırları
5/3/3 saniyedir. TCG yazılım emülasyonu için açık `--case-timeout-scale 4` profili
20/12/12 saniye kullanır; çarpan her uygulama vakasında ve konuk bağlamında
kaydedilir. `--timeout-scale` native pytest'te ayrıca seçilebilir. Kimlik, veri,
çıkış kodu ve kaynak temizliği beklentileri değişmez. Bunlar gerçek zamanlılık
veya performans hedefi değildir. Native GitHub runner profili henüz doğrulanmadı.
Konuk x86_64 Linux'tur; NIC, disk ve KVM eklenmez. O1/ARM64 emülasyonu değildir.

Tek vaka için:

```sh
python3 tools/run_can_suite_vm.py --guest-root .vm-root --wheels .vm-wheels --output artifacts/can-one --pytest-node 'tests/can/test_receiver.py::test_receiver_classic_lengths[c-one]' --expected-tests 1
```

Bu rapor `selected_tests` kapsamındadır; tam matrisin 36 vakalık kabulüyle
karıştırılmaz. Sıfır vaka başarı üretmez.

## Önerilen gerçek kaynak düzeltmesi

Özgün C göndericisi `ioctl(SIOCGIFINDEX)` dönüş kodunu kontrol etmeden
`ifr.ifr_ifindex` alanını kullanıyor. Var olmayan isimde bu alan geçerli bir
arayüz indeksi değildir; hata bind/gönderim aşamasına taşınabilir. Test, arayüzün
indeksi kullanılmadan ve veri gönderilmeye çalışılmadan reddedilmesini ister.

`patches/0001-can-c-sender-check-interface-index.patch` yalnızca bu çağrının
hatasını kontrol eder, tanı yazar, soketi kapatır ve 1 ile çıkar. Normal gönderim
ve mesaj sözleşmesi değişmez. `prepare_can_fix.py`, `git apply --check` sonrasında
yamayı yeni bir kopyaya uygular. 24 girdinin özetleri karşılaştırılır; yalnızca
C gönderici dosyası değişebilir. Özgün kaynak özetleri tekrar doğrulanır. Çıktı
dizini yeni olmalıdır; önceki kopya üzerine yazılmaz. Gerekçe ve katkı taslağı
[WP05_UPSTREAM_ISSUE.md](WP05_UPSTREAM_ISSUE.md) dosyasındadır.

VM'de düzeltilmiş tam matrisi çalıştırmak için:

```sh
python3 tools/prepare_can_fix.py --output build/can-fixed
python3 tools/run_can_suite_vm.py --guest-root .vm-root --wheels .vm-wheels --source-root build/can-fixed --output artifacts/can-fixed-guest
```

Özgün sürümdeki sorunu tek vakayla yeniden üretmek için `--source-root` vermeden
`--pytest-node 'tests/can/test_arguments.py::test_can_argument_error[nonexistent-c.sender]' --expected-tests 1`
seçeneklerini kullanın. Bu testin başarısız olması gerçek regresyon kaydıdır;
normal sonuç olarak yeşile çevrilmez. CI'nin CAN işi önerilen yamanın kopyasını
sınar; yama ve kaynak özetleri upload edilir. GitHub'da henüz çalıştırılmadı.

## Kontrollü hata deneyi

```sh
python3 tools/check_can_mutation.py --guest-root .vm-root --wheels .vm-wheels --output artifacts/can-controlled-failure
```

Özel kaynak kopyasında C alıcının yalnızca ID `0x123` için yazdırdığı DLC'ye 1
eklenir. Hazırlık mesajı değişmez. Yeniden derlenmiş kopyaya gerçek vcan üzerinden
bir baytlık çerçeve verilir. Testin DLC/hex uyuşmazlığıyla başarısız olması,
kaynakların temizlenmesi ve özgün dosyanın değişmemesi gerekir. Başka bir ortam
hatası bu deneyin başarısı sayılmaz.

`controlled-failure.json` deney sonucudur. Altındaki gerçek JUnit'te bir testin
başarısız kalması beklenir; sonuç yeşile çevrilmez. `change.patch`, derleme ve
süreç kayıtları değişikliği gösterir. Bu deney upstream kusuru iddiası değildir.

## Kanıtlar ve sınırlar

`case.json` senaryo/UID/girdi/çıktıyı, `console.log` ham terminali,
`process.json` sinyal/çıkış/temizliği ve `lease.json` sahipliği kaydeder. Süreç,
referans soketi ve PTY fd'leri kapanır; en son fixture kendi vcan arayüzünü siler.
Hatalı senaryoların günlükleri korunur.

İlk toplu VM denemesi 240 saniyelik bütçede kanıt aktarımına ulaşamadı. Zaman
aşımı kaydı `wp05-vcan-timeout-attempt/` altında başarısız olarak saklanır.
Başlangıç incelemesinde kernelin `/init` ve CAN modüllerine ulaştığı görüldü;
toplam VM bütçesi genişletildi. Sonraki Python zaman aşımlarının ardından
hazırlık denemeleri düzeltildi ve yukarıda açıklanan TCG profili eklendi. Güncel
konuk başlangıç aşamalarını ve
pytest ilerlemesini anında seri konsola, host süreç yöneticisi de ham günlükleri
okuma anında dosyaya yazar. Sonuç yokluğu başarı kabul edilmez.

Güncel kaynak kilidi 24 özgün dosyadır. Python alıcının iki dosyası aynı referans
commit'ten Git blob ve SHA-256 kontrolüyle eklendi. Önceki 22 dosyalık kilit
`docs/wp04-source.lock.json` içinde korunur.

Fiziksel hat, transceiver, bit zamanlaması, CRC enjeksiyonu, bus-off ve gerçek
zamanlılık kapsam dışıdır. 3×3 dil eşleştirmesi ve sanitizer ile uzun arayüz
girdileri P1 genişletmeleridir. Ortak hata tekrar üretimi WP-07'de, sıradaki
seri port/PTY senaryoları WP-06'dadır.

Dayanak: [Linux SocketCAN belgeleri](https://docs.kernel.org/networking/can.html).
