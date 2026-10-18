# Yetkisi kısıtlı host için isteğe bağlı Linux konuğu

Normal Linux/VM üzerinde `run-linux-wp01.sh` tercih edilir. Buradaki yol,
host CAN soketlerini veya ağ yetkilerini vermiyorsa kullanılabilecek teknik
deneydir. Guest kendi Linux çekirdeğini ve vcan modüllerini çalıştırır.

Bu sayfadaki `run_can_vm.py`, WP-01'in C referans deneyidir. Aynı kernel/QEMU
köküyle pytest ve altı CAN girişini UID 1000 ile çalıştıran güncel yol için
[WP05_CAN_MATRIX.md](WP05_CAN_MATRIX.md) içindeki `run_can_suite_vm.py` komutunu kullanın.

Çalıştırılmış ortam: Ubuntu 24.04 uyumlu x86_64 kullanıcı alanı, GCC ve statik
glibc geliştirme dosyaları, QEMU 8.2.2 ve Linux 6.8.0-138-generic. KVM gerekmez.
Bu script x86_64 ile sınırlıdır. Konuk uygulama O1/ARM64 binary'si değildir.

## Konuk dosyaları

`run_can_vm.py --guest-root` altında şu yerleşimi bekler:

| Yol | İşlev |
| --- | --- |
| `usr/bin/qemu-system-x86_64` | Kullanıcı alanında QEMU |
| `usr/lib/x86_64-linux-gnu/` | QEMU kitaplıkları ve `qemu/accel-tcg-x86_64.so` |
| `usr/share/qemu/` ve `usr/share/seabios/bios-256k.bin` | Firmware |
| `usr/bin/busybox` veya `bin/busybox` | Statik BusyBox |
| `boot/vmlinuz-6.8.0-138-generic` | Linux çekirdeği |
| `lib/modules/6.8.0-138-generic/` | Aynı sürümün can/can-raw/can-dev/vcan modülleri |

Kullanılan resmi Ubuntu paketleri, sürümleri, boyutları, SHA-256 özetleri ve
snapshot adresi `vm-packages.lock.json` dosyasında bulunur. Bütün paketler resmi
Ubuntu APT metadata'sındaki boyut/özet ile karşılaştırıldı. Paketler sistemde
kurulmadı; `dpkg-deb -x` ile tek bir dizine açıldı. QEMU, glibc gibi bazı temel
kitaplıkları host kullanıcı alanından kullanır; bu yüzden bu yöntem rastgele
bir Linux dağıtımında taşınabilir çalıştırma ortamı vaadi değildir.

Paketleri aynı snapshot'tan indirmek için aşağıdaki Python örneği kullanılabilir.
Yaklaşık 187 MB indirir; açılmış dosyalar için daha fazla alan gerekir.
Bu indirme örneği bu teslim sırasında ayrıca uçtan uca çalıştırılmadı; gerçek
paketler APT/curl ile alındı ve aynı kilide göre doğrulandı.

```python
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json
import subprocess

lock = json.loads(Path("docs/vm-packages.lock.json").read_text())
cache = Path(".vm-cache")
root = Path(".vm-root")
cache.mkdir(exist_ok=True)
root.mkdir(exist_ok=True)
for item in lock["packages"]:
    package = cache / Path(item["filename"]).name
    if not package.exists():
        with urlopen(lock["snapshot"] + item["filename"], timeout=120) as response:
            package.write_bytes(response.read())
    data = package.read_bytes()
    assert len(data) == item["size_bytes"], package
    assert hashlib.sha256(data).hexdigest() == item["sha256"], package
    subprocess.run(["dpkg-deb", "-x", str(package), str(root)], check=True)
```

Host araçları: `python3`, `gcc`, `make`, `dpkg-deb`, `zstd`. Statik bağlama için
Ubuntu'da `libc6-dev` gerekir; `build-essential` bunu sağlar. Kernel modüllerinin
`.zst` sıkıştırmasını açmak için `zstd` kullanılır.

## Çalıştırma

```sh
python3 tools/run_can_vm.py --guest-root .vm-root --output artifacts/can-guest
```

Araç kaynak özetlerini doğrular; özgün göndericiyi kendi Makefile'ıyla statik
derler, bağımsız C alıcıyı derler ve Python ile minimal bir `newc` initramfs üretir.
Host üzerinde `mknod`, modprobe veya ağ arayüzü oluşturma işlemi yapmaz.

QEMU'ya ağ kartı eklenmez. Konuk içindeki betik vcan oluşturur, alıcı/göndericiyi
çalıştırır, kendi arayüzünü siler ve konuğu kapatır. Alıcı ilk çerçeveyi alınca
SIGINT gönderir; sabit bir uyku süresi doğru veri geldiğinin kanıtı sayılmaz.

`run.json` ve `guest-console.log` gerçek sonucu taşır. 90 saniyelik toplam
QEMU süresi aşılırsa çalıştırma başarısızdır; gözlenen çıktı yine saklanır.
Binary ve initramfs özetleri kaydedilir. Derleme sırasında mutlak yol bilgisinin
binary'ye girmesi nedeniyle başka bir klasördeki binary özetinin aynı olması
garanti edilmez; kaynak özetleri ve gözlenen protokol verisi karşılaştırılmalıdır.

Bu konuk CAN deneyini tekrarlar. Native seri/PTY deneyi ayrıca `wp01.py serial`
ile çalıştırılır; burada tam GitHub Actions runner ortamı emüle edilmez.
