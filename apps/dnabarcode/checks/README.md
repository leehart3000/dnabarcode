# Known-answer checks

A regression set: known sequences sent to every new image before it is
pushed (see `.github/workflows/deploy-dnabarcode.yml`). Each `<name>.json`
is an `/identify` request body and `<name>.expected` the answer it must give:
the answer text, or `declined: <reason>` (an expected file may hold just the
start of the text). Any change in an answer stops the deploy until the check
is updated on purpose.

Add or refresh a check with `scripts/add_check.py`, which identifies the
sequence with a local bundle and writes both files; review the answer before
committing.

| Check | Source | Guards |
|---|---|---|
| `aedes-aegypti-HQ945416` | GenBank HQ945416.1, *Ae. aegypti* COI barcode | A species answer |
| `aedes-aegypti-HQ945416-reverse` | The same, reverse complemented | Reading the other strand |
| `aedes-aegypti-HQ945416-first200` | Its first 200 bases | A short fragment |
| `aedes-aegypti-mitogenome-NC_035159` | RefSeq NC_035159.1, *Ae. aegypti* mitochondrial genome (lab strain) | Finding the barcode in a long sequence; a cautious genus answer |
| `aedes-aegypti-mitogenome-PQ197330` | GenBank PQ197330, *Ae. aegypti* mitochondrial genome | Finding the barcode; a species answer |
| `culex-pipiens` | A *Cx. pipiens* COI barcode | A complex answer |
| `anopheles-gambiae-mitogenome-NC_002084` | RefSeq NC_002084.1, *An. gambiae* mitochondrial genome | Finding the barcode in another genus; a complex answer |
| `aedes-albopictus-refseq` | RefSeq COI of *Ae. albopictus* (from the committed anchors) | Not confused with *Ae. aegypti* |
| `human-mitogenome-NC_012920` | RefSeq NC_012920.1, human mitochondrial genome | A non-mosquito animal: a broad group only |
| `declined-too-short` | The first 80 bases of HQ945416.1 | Declining under 100 bases |
| `declined-protein` | A protein sequence | Declining protein |
| `declined-two-sequences` | Two FASTA records | Declining several sequences |
| `declined-fastq` | A FASTQ read | Declining raw reads |
