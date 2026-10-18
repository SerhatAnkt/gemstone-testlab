# Upstream katkı taslağı — C CAN göndericisinde arayüz indeksi hatası

Referans: `t3gemstone/examples`, commit
`2619a7584d39203a057abc08ab7c6698dc476868`.
Dosya: `canbus/c/sender/main.c`.

## Yeniden üretilen davranış

Olmayan bir arayüz adı verildiğinde `ioctl(SIOCGIFINDEX)` hata döndürüyor.
Özgün C göndericisi dönüş değerini kontrol etmiyor; doldurulmamış
`ifr.ifr_ifindex` alanını `bind` için kullanıyor. Kaydedilmiş Linux misafir
çalışmasında indeks 0 yazdırıldı, normal mesaj gönderilmeye çalışıldı ve ancak
gönderim aşamasında `No such device or address` hatası geldi. Başka bir ortamda
doldurulmamış alanın aynı değerde olması beklenmez.

Linux SocketCAN'de indeks 0 herhangi bir arayüze bağlanma anlamına gelir.
İstenen arayüzün bulunamaması bu davranışa düşmemelidir. C++ göndericisi ve
alıcılar zaten indeks sorgusunun hata sonucunu kontrol ediyor.

TestLab'ın `CAN-ARG-02` vakası, mevcut olmayan arayüzün indeksi kullanılmadan
ve gönderim denenmeden, açıklayıcı hatayla reddedilmesini ister. Çıkış 1'dir;
takılma veya zorunlu öldürmeyle başarı üretilmez.

## Önerilen düzeltme

`patches/0001-can-c-sender-check-interface-index.patch` yalnızca çağrının hata
sonucunu kontrol eder, tanı yazar, soketi kapatır ve `EXIT_FAILURE` döndürür.
Normal gönderim akışı ve `can_examples_v1` mesajları değişmez. Yama özgün
kaynak klasörüne otomatik uygulanmaz; `tools/prepare_can_fix.py` yeni bir
kopyada `git apply --check` ve `git apply` çalıştırır. Kaynak özetlerinde yalnızca
bu dosyanın değiştiği ve özgün ağacın değişmediği doğrulanır.

## English PR draft

Title: **canbus/c: check SIOCGIFINDEX before binding the sender**

When the requested CAN interface does not exist, the C sender ignores the failed
SIOCGIFINDEX call and uses an uninitialized interface index. In the reproduced
Linux vcan run it used index zero, reached the transmit loop, and failed only
when writing a frame. Check the ioctl result, report the interface lookup error,
close the socket, and return EXIT_FAILURE before binding.

The TestLab regression verifies that a nonexistent interface is rejected before
its index is used or transmission is attempted. The normal sender contract is
validated separately with an independent SocketCAN observer. Detailed baseline,
fixed-tree results and the exact execution scope are recorded in RESULTS.md and
the attached project artifacts.

## Kanıt ve sınır

Gerçek test sayıları ve kaynak profilleri [RESULTS.md](../RESULTS.md) içindedir.
`case.json`, ham stdout/stderr, JUnit, kaynak/binary özetleri ve süreç temizliği
kayıtları korunur. Bu taslak ve yama henüz GitHub'a gönderilmedi. Sonuçlar x86_64
Linux vcan kapsamındadır; O1, fiziksel CAN veya ARM64 çalışma kanıtı değildir.

Dayanak: [Linux SocketCAN arayüze bağlanma belgesi](https://docs.kernel.org/networking/can.html#how-to-use-socketcan).
