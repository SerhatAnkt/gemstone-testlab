# WP-06 — yeniden üretilmiş seri kusurları ve katkı taslakları

Bu bulgular `2619a7584d39203a057abc08ab7c6698dc476868` sürümü içindir.
Güncel upstream başında aynı kusurların sürdüğü iddia edilmez. Issue veya PR
gönderilmedi. Özgün paket kaynakları değişmedi; aşağıdaki dört yama yalnızca
`prepare_serial_fixes.py` ile oluşturulan özel kopyada sınandı.

## 1. C ve C++ seri RX satır sonlarını değiştiriyor

Varsayılan Linux PTY ayarlarında `ICRNL` açıktır. `configure_serial` ve
`SerialPort::configure` bu bayrağı kapatmıyor. Gerçek uçtan
`5258007f80ff0d0a0d454e44` gönderilince konsolda
`5258007f80ff0a0a0a454e44` gözlendi. Uzun parça senaryosunun son CR/LF parçası da
iki dilde bozuldu. Dört gerçek test başarısızlığı kaydedildi.

Yama: `patches/0002-serial-preserve-raw-input-bytes.patch`.
ICRNL/INLCR/IGNCR ile raw aktarımı bozan şerit/parity işleme bayrakları kapatılır.
Test fixture cihazı önceden raw moda almadığı için bu uygulama kusurunu yakalar.

Önerilen PR başlığı: **Preserve serial input bytes in C and C++ terminals**

Önerilen açıklama:

> With the default terminal input flags, CR bytes are translated to LF in the
> C and C++ serial examples. Clear input translation and parity-processing flags
> when configuring raw serial I/O. Independent Linux PTY tests compare CR/LF,
> NUL and high bytes without normalizing the received data.

## 2. C ve C++ kısmi baud sayılarını kabul ediyor

`atoi("9600oops")` ve `std::atoi("9600oops")`, 9600 döndürür. Geçersiz parametre
reddedilmeden cihaz açılıp `Serial terminal started.` yazdırıldı. Sonrasında
stdin pipe olduğu için terminal kurulumu hata verdi; bu son hata, geçersiz baud'un
doğru fazda reddedildiği anlamına gelmez. İki test başlangıç metnini denetleyerek
bu yanlış başarıyı yakaladı.

Yama: `patches/0003-serial-reject-partial-baud-arguments.patch`.
`strtol` ile bitiş işaretçisi, boş dönüşüm, `ERANGE`, pozitiflik ve `INT_MAX`
sınırı denetlenir. Geçerli sayının desteklenen hız listesiyle kontrolü sürer.

Önerilen PR başlığı: **Reject malformed baud arguments before opening the serial device**

Önerilen açıklama:

> The current integer conversion accepts numeric prefixes such as 9600oops.
> Validate the complete conversion and range before initializing the device.
> PTY-backed CLI tests cover zero, nonnumeric, unsupported and partially numeric
> baud arguments and require rejection before the startup message.

## 3. Python konsol aktarımı, tampon ve select yüzünden takılıyor

Tek yazımla gönderilen konsol metninin tamamı seri tarafta alınamadı. `select`
çekirdekteki fd'yi izler; `sys.stdin.buffer.read(1)` ise kalan baytları Python
tamponuna önceden alabilir. Sonraki `select` bu kullanıcı alanı tamponunu görmez.
İlk bayttan sonra yeni konsol girdisi beklenebilir. İki toplu TX ve bir parçalı
aktarım testi, 10 saniyelik senaryo sınırında başarısız oldu. Günlüklerde kısmi
seri çıktı korunur.

Yama: `patches/0004-serial-python-read-unbuffered-stdin.patch`.
Konsol aynı fd'den `os.read(stdin_fd, 1)` ile tampon olmadan okunur. Bu küçük yama
uygulamanın mevcut tek baytlık işleyişini korur; yeni protokol veya thread eklemez.
Üç başarısız aktarım testi yama kopyasında geçti. `-u`, stdout/stderr için
verilmişti; bu deneyde stdin sorununun devam ettiği ayrıca gözlendi.

Önerilen PR başlığı: **Read stdin without buffering in the Python serial select loop**

Önerilen açıklama:

> Burst console input can remain in the buffered stdin reader after select has
> consumed the kernel readiness event. Read from the selected descriptor with
> os.read. Independent PTY tests send complete bursts and fragmented binary data
> and require every byte to reach the serial peer within a bounded deadline.

## 4. Python yardımı yanlış hata kodu döndürüyor

`argparse`, `-h` ve `--help` için `SystemExit(0)` üretir. Mevcut genel yakalama
bunu 1'e çeviriyor. İki yardım testi doğru yardım metnine rağmen kod 1 gözledi.

Yama: `patches/0005-serial-python-preserve-argparse-exit-code.patch`.
`SystemExit.code` korunur: yardım 0, argparse hatası 2 olur. Zorunlu argüman
hataları için test sözleşmesi anlaşılır tanı ve sıfır olmayan kod ister.

Önerilen PR başlığı: **Preserve argparse exit codes in the Python serial CLI**

Önerilen açıklama:

> Help currently prints correctly but exits with failure because all SystemExit
> exceptions are converted to 1. Return argparse's exit code so both help flags
> succeed and parse errors retain their normal nonzero status. Tests cover both
> help flags, missing options and malformed baud input.

## Doğrulama ve ayrım

| Bulgu | Özgün başarısız vaka | Önerilen yama kopyası |
| --- | ---: | --- |
| CR/LF dönüşümü | 4 | Geçti |
| Kısmi baud sayısı | 2 | Geçti |
| Python tamponlu konsol okuması | 3 | Geçti |
| Python yardım çıkış kodu | 2 | Geçti |
| **Toplam** | **11** | **45/45 seri testi geçti** |

İlk profilin 34 başarısı ve 11 başarısızlığı gerçek JUnit'te korunur. Hatalar
xfail, skip, çıktı normalleştirme veya veri tekrarlarıyla gizlenmedi. Dört yama
toplam beş dosyayı değiştirir; her biri bağımsız katkı olarak gözden geçirilebilir.
WP-05'in CAN C gönderici yaması bu dört düzeltmeden ayrıdır.

Gerçek PTY testinin kasıtlı TX bozulmasını da yakaladığı doğrulandı; bu yapay hata
buradaki dört upstream bulgusunun bir parçası değildir. İlgili kanıtlar ve komutlar
[WP06_SERIAL.md](WP06_SERIAL.md) içindedir.
