# Test data

There is no patient data in this repository. This folder names the public cases the numbers in
this project are measured on, and fetches them.

```
uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py --list
uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py
uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py --case C3N-01524
```

The files land in `Contents/data/dicom`. Import that folder in 3D Slicer's DICOM module, or add it as
a database in SlicerAlbula. The script does not write into a Slicer database itself.

## The cases

| case | collection | what | size | why |
|---|---|---|---|---|
| `C3N-01524` | CPTAC | CT, 709 slices | 839 MB | the surface-extraction case. Segmented with `ts:total`, a correct extraction gives 12,121,372 triangles |
| `CRLM-CT-1058` | Colorectal-Liver-Metastases | CT, 43 slices | 23 MB | small; a quick round trip |
| `HCC_044` | HCC-TACE-Seg | CT, 87 slices | 46 MB | liver, contrast phases |
| `ReMIND-035` | ReMIND | MR, 176 slices | 20 MB | brain MR, the FastSurfer input |
| `ReMIND-035` | ReMIND | 2 × SEG | 5 MB | segmentations from the archive, to test our reader on files we did not write |

932 MB in total, measured. If you only want to try the application, `--case CRLM-CT-1058` is
23 MB and exercises the same path.

## Where they come from

The [Imaging Data Commons](https://portal.imaging.datacommons.cancer.gov) resolves a series from
its SeriesInstanceUID with no login. `series.tsv` has one line per series; the UID in it is the
public identifier. If the script cannot fetch one, it says which and continues.

## What is not here

Nothing generated on the development machine. Every UID in `series.tsv` begins
`1.3.6.1.4.1.14519`, the archive's own root; anything made locally carries a `2.25.*` UID and
cannot be on the list by accident.

The development database also held one non-public study. It is excluded, not named, and none of
its identifiers appear in this repository.

## Licence and citation

Every collection is **CC BY** — 3.0 or 4.0, all attribution licences — as recorded in IDC's index
for each series. Use of the data requires citing the collection, and IDC asks to be cited as well.
The citations below are IDC's own, from `citations_from_selection` in `idc-index`:

- Moawad, A. W., Fuentes, D., Morshid, A., Khalaf, A. M., Elmohr, M. M., Abusaif, A., Hazle, J. D., Kaseb, A. O., Hassan, M., Mahvash, A., Szklaruk, J., Qayyom, A., & Elsayes, K. (2021). *Multimodality annotated HCC cases with and without advanced imaging segmentation* (Version 1) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/TCIA.5FNA-0924

- National Cancer Institute Clinical Proteomic Tumor Analysis Consortium (CPTAC). (2018). *The Clinical Proteomic Tumor Analysis Consortium Clear Cell Renal Cell Carcinoma Collection (CPTAC-CCRCC)* (Version 14) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/K9/TCIA.2018.OBLAMN27

- Simpson, A. L., Peoples, J., Creasy, J. M., Fichtinger, G., Gangai, N., Lasso, A., Keshava Murthy, K. N., Shia, J., D'Angelica, M. I., & Do, R. K. G. (2023). *Preoperative CT and Survival Data for Patients Undergoing Resection of Colorectal Liver Metastases (Colorectal-Liver-Metastases)* (Version 2) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/QXK2-QG03

- Juvekar, P., Dorent, R., Kögl, F., Torio, E., Barr, C., Rigolo, L., Galvin, C., Jowkar, N., Kazi, A., Haouchine, N., Cheema, H., Navab, N., Pieper, S., Wells, W. M., Bi, W. L., Golby, A., Frisken, S., & Kapur, T. (2023). *The Brain Resection Multimodal Imaging Database (ReMIND)* (Version 1) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/3RAG-D070

- Fedorov, A., Longabaugh, W. J. R., Pot, D., Clunie, D. A., Pieper, S. D., Gibbs, D. L., Bridge, C., Herrmann, M. D., Homeyer, A., Lewis, R., Aerts, H. J. W. L., Krishnaswamy, D., Thiriveedhi, V. K., Ciausu, C., Schacherer, D. P., Bontempi, D., Pihl, T., Wagner, U., Farahani, K., et al. (2023). National Cancer Institute Imaging Data Commons: Toward Transparency,                     Reproducibility, and Scalability in Imaging Artificial                     Intelligence. RadioGraphics, 43(12). https://doi.org/10.1148/rg.230180

