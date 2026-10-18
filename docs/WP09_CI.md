# WP-09 — ortak CI yürütme ve kabul denetimi

CI altyapısı uygulandı. **Yerel kabul ile gerçek GitHub runner kabulü ayrıdır.**
Proje deposu artık [SerhatAnkt/gemstone-testlab](https://github.com/SerhatAnkt/gemstone-testlab) olarak oluşturuldu.
**Uzak kabul geçti:** [koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) içinde
beş iş başarılı oldu. Aynı koşunun dört profil kanıtı indirilip yeniden doğrulandı. Aşağıdaki WP-09 yerel deneyleri
tarihsel kanıttır; yeni bir hosted koşu olarak yeniden etiketlenmez.

## Bir komutla bir profil

Linux x86_64 ve Python 3.12 kullanılır. Host/CAN için `tests/requirements.txt`,
seri için `tests/requirements-serial.txt` bağımlılıkları hash kontrolüyle
kurulur. ARM64 derleme Python test paketlerine ihtiyaç duymaz; WP-08'in
doğrulanmış SDK'sını kullanır.

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements-serial.txt
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/ci-host
.venv-testlab/bin/python -m tests.testlab ci --profile serial --source-profile proposed-fixes --output artifacts/ci-serial
.venv-testlab/bin/python -m tests.testlab ci --profile can --source-profile proposed-fixes --output artifacts/ci-can
python3 -m tests.testlab ci --profile aarch64 --toolchain-root build/gemstone-sdk --output artifacts/ci-aarch64
```

Her `--output` yeni bir dizindir. CAN komutu normal kullanıcıyla çalışır;
`iproute2`, `vcan` modülü ve yalnız ayrıcalıklı ağ işlemlerini yapacak
`sudo -n` gerekir. Eksik önkoşul `error` ve sıfırdan farklı çıkış üretir.
Root olarak CAN testi başlatmak da kabul edilmez. SDK kurulumu için
[WP08_CROSS_BUILD.md](WP08_CROSS_BUILD.md) kullanılır.

| Profil | İşlem | Zorunlu matris |
| --- | --- | --- |
| `host` | Altı native derleme ve host testleri | 66 kayıtlı vaka |
| `serial` | İki native derleme, gerçek konsol/device PTY'leri | 45 kayıtlı vaka |
| `can` | Dört native derleme, bağımsız SocketCAN uçları | 36 kayıtlı vaka |
| `aarch64` | SDK kimliği, altı çapraz derleme, ELF/readelf | Altı AArch64 ELF; hedefte çalıştırma yok |

`tests/ci-contract.json` zorunlu node ID'lerini ve hedefleri tanımlar.
Yeni eklenen testler de çalışır; kayıtlı vakaların silinmesi veya seçimin
daraltılması kabulü bozar. Bir vaka bilinçli kaldırılacak/yeniden adlandırılacaksa
bu sözleşme de incelenerek güncellenir. CI sözleşmesini kendiliğinden yeniden
üretip eksik vakaları gizlemez.

## Hangi kaynak sınanır?

Varsayılan `--source-profile working-tree`, mevcut çalışma ağacını olduğu gibi
derler ve sınar. Kaynakları eski upstream commit'ine sıfırlamaz. `--source-root`
yerel bir ağaç seçebilir; hosted kabulde kaynak, sınanan checkout'un içinde
olmalıdır.

Paket özgün upstream dosyalarını koruduğu için seri ve CAN işlerinde açıkça
`--source-profile proposed-fixes` seçilir. Bu mod mevcut dosyaları özel bir
kopyaya alır ve beş önerilen yamanın ilgili olanlarını uygular. Raporda özgün
girdi ve gerçekten sınanan yama kopyası **ayrı özetlerle** görünür. Bu modun
başarısı, özgün kusurlu sürümün başarılı olduğu anlamına gelmez.
Yamalar kaynaklara entegre edildiğinde CI `working-tree` moduna geçirilmelidir;
aynı yamanın ikinci kez uygulanması sessizce atlanmaz.

Yama kopyası bir Git deposunun altındayken üst checkout'un Git bağlamına
girilmesi sorunu bu aşamada gerçek bir denemeyle bulundu. İki hazırlık aracı
artık kendi özel kopyasında çalışır; dış `GIT_*` ayarlarını taşımaz ve üst
depo keşfini durdurur. Özgün dosyalar korunur. Gerçek parent Git deposu ve
yanlış `GIT_DIR/GIT_WORK_TREE` ile regresyon testi eklendi.

## Yeşil sonuç için gerekenler

`ci` komutu alt süreçleri ortak süreç yöneticisiyle başlatır. Dış
`PYTEST_ADDOPTS/PYTEST_PLUGINS` değerleri test seçimini değiştiremez. Kaynak ve
harness içerikleri başlangıçta kaydedilip sonda karşılaştırılır.

- Derleme matrisi tamdır; tüm hedefler geçer ve ELF mimarileri kabul edilir.
- Pytest gerçekten çalışmıştır. Sıfır vaka, yalnız `--collect-only`, skip,
  eksik zorunlu node veya sıfırdan farklı pytest kodu kabul edilmez.
- Her vakanın setup/call/teardown fazı geçmiştir; ortak JSON ile JUnit sayıları
  uyuşur. Ham pytest kodu raporda korunur; CI'nin etkin çıkış kodu ayrıca vardır.
- Vaka kanıtları ile tüm CI kanıt dosyalarının boyut/SHA-256 değerleri uyar.
- Yönetilen süreç grupları, liderler, pipe'lar ve selector'lar temizlenmiştir.
- Sahipli vcan arayüzleri kaldırılmıştır; yabancı arayüze dokunulmamıştır.

Sahiplik testi bilinçli olarak önce yanlış token ile silmeyi reddettirir,
sonra doğru kimliği geri getirip kendi arayüzünü temizler. İlk ret raporda
kalır. Kabul denetimi bu geçmişi silmez; **son doğrulanmış temizlik durumunu**
değerlendirir. Geride kalan arayüz veya yabancı kaynağa müdahale kabul edilmez.

`ci.json` şeması `docs/ci.schema.json` içindedir. Çıkış `0` kabul, `1` test/
derleme/kabul başarısızlığı, `2` önkoşul veya altyapı hatasıdır. Eksik pytest
paketi de kurulum hatasıdır; bir boş çalışma başarılı sayılmaz.

## Dört kanıtın birleştirilmesi

```sh
python3 -m tests.testlab ci-verify \
  --report artifacts/ci-host/ci.json \
  --report artifacts/ci-serial/ci.json \
  --report artifacts/ci-can/ci.json \
  --report artifacts/ci-aarch64/ci.json \
  --output artifacts/acceptance.json
```

Tam olarak dört farklı profil gerekir. Denetim her paketin dosyalarını ve
test/derleme matrisini tekrar inceler; kaynak, harness, sözleşme ve commit
kimliklerini karşılaştırır. Tek bir eksik/değişmiş paket toplam kabulü bozar.
Yerel sonuç `github_hosted_runner: not_executed` olarak kalır.

Hosted kullanımda `--require-hosted` eklenir. Beklenen commit,
`TESTLAB_EXPECTED_COMMIT`; dört job'un sonuçları `TESTLAB_JOB_RESULTS` üzerinden
gelir. Dört profil aynı repository/run ID/attempt'a ait olmalı, mevcut kabul
işinin bağlamıyla eşleşmeli ve tüm işler `success` olmalıdır. Skip/cancel/failure
ve önceki koşudan kalma kanıt kabul edilmez. Tam kabul için workflow'un tümünü
aynı attempt'ta yeniden çalıştırmak gerekir.

Dosya özetleri kazara değişmiş veya eksik kanıtı yakalar; bunlar kriptografik
bir runner tasdiki değildir. Uzak kabul, gerçek GitHub koşusunun bağlantısı ve
saklanan kanıtlarıyla birlikte incelenir.

## GitHub Actions akışı

`.github/workflows/testlab.yml` beş iş içerir:

1. `host-checks`: altı native hedef ve host matrisi.
2. `serial-integration`: açık yama kopyası, PTY matrisi ve gerçek TX bozulması.
3. `linux-integration`: normal kullanıcıyla gerçek vcan matrisi.
4. `aarch64-cross-build`: kilitli SDK, altı AArch64 hedef; hedefte çalışma yok.
5. `acceptance`: önceki dört işin kanıtlarını indirip zorunlu toplam kabulü verir.

PR'da `pull_request.head.sha`, diğer olaylarda `github.sha` checkout edilir.
CLI gerçek checkout HEAD'ini beklenen değerle karşılaştırır; uyuşmazsa derleyici
ve pytest başlamaz. Hosted checkout'ta commit dışı proje değişikliği de
reddedilir. İşler Python/SDK bağımlılıklarını kendileri kurar.

Kanıtlar `if: always()` ile 14 gün saklanır. Her profil kendi artifact'ini
üretir; son kabul işi başarısız/skipped işleri de görür. Test komutları `tee`
arkasında kalmaz; CLI'nin gerçek çıkışı job sonucuna taşınır. Eksik artifact
veya eksik `ci.json` son kabulü başarısız yapar. Workflow izinleri `contents: read`.
`actionlint` v1.7.12 ile sözdizimi ve Actions ifadeleri yerelde doğrulandı;
ShellCheck/pyflakes bu denetimde çalıştırılmadı.

## Çalıştırılmış yerel deneyler

| Deney | Sonuç |
| --- | --- |
| Host CI | 66 test, altı native hedef geçti |
| Seri CI — açık yama kopyası | 45 gerçek PTY testi geçti |
| CAN CI — açık yama kopyası | Ayrı x86 Linux konuğunda gerçek vcan; 36 test, UID 1000 |
| ARM64 CI | Altı AArch64 ELF; SDK doğrulaması geçti |
| 12 CI regresyonu | Boş/kısmi/skip/koleksiyon, kanıt/commit/mimari ve temizlik hataları reddedildi |
| Gerçek yerel Git commit deneyi | İlk commit geçti; ikinci commit'teki gerçek `#error` derlemeyi kırdı; eski commit beklenince araçlar başlamadı |
| Root ile CAN CI | Önkoşul hatası, CLI 2; boş/skip başarı yok |
| Beş Actions işi | Hash'i doğrulanan actionlint aracıyla statik kontrol geçti |

Yerel Git deneyi yeniden çalıştırılabilir; geçici, yayınlanmamış bir checkout
oluşturur. Kullanıcının kaynaklarını veya uzak GitHub depolarını değiştirmez:

```sh
python3 tools/check_ci_current_tree.py --toolchain-root build/gemstone-sdk --output artifacts/current-pr-check
```

Konuk CAN CI komutu, [VM_REPRODUCTION.md](VM_REPRODUCTION.md) içindeki runtime
hazırlandıktan sonra çalışır:

```sh
python3 tools/run_can_suite_vm.py --ci-profile --guest-root /tam/yol/guest-root --wheels /tam/yol/wheels --output artifacts/can-ci-vm
```

Bu yardımcı C/C++ hedefleri host'ta derleyip, kaynak özetine ve ELF/hash
kontrollerine bağlı prebuilt dosyaları konuğa verir. CI'nin CAN komutu konukta
UID 1000 ile çalışır; hazırlık yamaları orada da açıkça uygulanır. Konukta GCC
ile derleme veya ARM64 emülasyonu yapıldığı iddia edilmez.

İlk CAN CI denemesinde pytest 36/36 geçmesine rağmen tarihsel temizlik ret
kaydının yanlış yorumlanması CI kodu 2'ye yol açtı. Bu başarısız deneme
`wp09-can-vm/` altında korunur. Son kabul `wp09-can-vm-final/` içindedir.
Toplu koleksiyonda iki `test_arguments.py` modülünün ad çakışması da bulundu;
CAN/seri dizinlerine paket işaretçileri eklenerek 147 vaka birlikte toplanabildi.

## Kanıt dizinleri ve açık kalan adım

`artifacts/wp09-host-final/`, `wp09-serial-final/`, `wp09-aarch64-final/` ve
`wp09-can-vm-final/guest-artifacts/ci-can/` birincil kabul girdileridir.
`wp09-acceptance/` birleşik kararları; `wp09-current-pr/` gerçek commit deneyini;
`wp09-clean-room/` temiz paketten tekrarları içerir. Önceki iş paketlerinin
raporları tarihsel olarak korunur, güncel koşu gibi yeniden etiketlenmez.

**Uzak kabul geçti:** `docs/ci-runs/39155570890.json` gerçek hosted kabulü
kaydeder. Önceki tam teslimdeki `artifacts/wp09-remote-status.json`, depo
oluşturulmadan önceki tarihsel engeldir. O1 donanımı,
fiziksel UART/CAN ve gerçek zamanlı davranış bu CI kabulünün dışında kalır.


## İlk hosted koşuda bulunan ortam farkları

İlk gerçek GitHub koşusunda host, seri ve AArch64 işleri geçti. CAN işi,
runner'ın `6.17.0-1022-azure` çekirdeğinde `vcan` bulunmadığı için kod 2 verdi.
İş akışı artık modül yoksa yalnız çalışan çekirdekle birebir eşleşen
`linux-modules-extra-$(uname -r)` paketini kurar ve modülü yükler. Kurulum veya
modül yükleme başarısızsa zorunlu CAN kabulü yine başarısız olur.

Aynı koşunun toplam denetimi, host test fixture'ındaki gizli
`.testlab-toolchain-install.json` dosyası artifact yüklemesinde dışlandığı için
eksik kanıtı reddetti. Altı upload adımı artık yalnız kendilerine ayrılmış
kanıt dizinlerinde `include-hidden-files: true` kullanır. Böylece inventory'ye
kaydedilen gizli dosyalar da taşınır; eksik dosya kontrolü gevşetilmez.

İlk başarısız koşu ve düzeltme sonraki başarılı koşudan ayrı kaydedilir.


## Doğrulanmış hosted kabul

[Koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) beş işi başarıyla tamamladı.
66 host, 45 seri ve 36 gerçek vcan vakası geçti; altı AArch64 ELF derlendi.
24 sahipli vcan arayüzü kaldırıldı. Altı artifact'in ZIP SHA-256 değerleri
GitHub metadata'sıyla karşılaştırıldı; dört profil `ci-verify` kurallarıyla
yerelde yeniden incelendi. Özgün hosted `acceptance.json`, aynı commit,
kaynak/harness özetleri ve `github_hosted_runner: passed` sonucunu taşır.

Kalıcı küçük özet: `docs/ci-runs/39155570890.json`. İlk başarısız koşu
`docs/ci-runs/39155256787.json` içinde ayrı korunur. Artifact'ler workflow'da
14 gün tutulur; bu süre geçince ham indirmeler erişilemeyebilir.
