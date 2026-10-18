# Gerçek GitHub CI kayıtları

| Koşu | Sonuç | Açıklama |
| --- | --- | --- |
| [#1](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155256787) | Başarısız | CAN modülü yok; gizli host kanıtı upload sırasında eksik. [Kayıt](39155256787.json) |
| [#2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) | Beş iş başarılı | 66 host, 45 seri, 36 vcan; altı AArch64 derleme; artifact'ler ayrıca yerelde doğrulandı. [Kayıt](39155570890.json) |

Kayıtlar gerçek commit, job ve artifact kimlikleriyle sonuçların kapsamını
gösterir. Küçük özetler Git'te korunur; ham artifact'lerin saklama süresi
workflow'da 14 gündür. O1 kartı veya ARM64 hedefte çalıştırma kanıtı değildir.
