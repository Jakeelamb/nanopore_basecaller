README_GIAB_Mapping_References.md was generated on 2021-04-01 by Sierra D. Miller.  
README_GIAB_Mapping_References.md was updated 2023-09-21 by Jennifer McDaniel. 

--------------------
GENERAL INFORMATION
--------------------

Title of Dataset: Reference genomes used by GIAB for mapping

Author Information
- Principal Investigator: Justin Zook (jzook@nist.gov)  
- Nate Olson (nathanael.olson@nist.gov)  
- Sierra Miller (sierra.miller@nist.gov)  
- Jennifer McDaniel (jennifer.mcdaniel@nist.gov)  

Date of data collection : 2021-04-01 though 2023-09-21

---------------------------
SHARING/ACCESS INFORMATION
---------------------------

#### Licenses/restrictions placed on the data, or limitations of reuse: CC0,
full NIST data use policy at the end of this document


#### Recommended citation for the data:  
  Towards a Comprehensive Variation Benchmark for Challenging Medically-Relevant Autosomal Genes
  Wagner et al. bioRxiv 2021.06.07.444885; doi: https://doi.org/10.1101/2021.06.07.444885 


#### Links to publicly accessible locations of the data: 
https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/


---------------------
DATA & FILE OVERVIEW
---------------------

File List:

**GRCh37**

hs37d5.fa.gz  
hs37d5.fa.gz.fai 
hs37d5.fa.gz.gzi  

**GRCh38**  

GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz  
GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz.fai  
GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz.gzi
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions.fasta.gz
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions.fasta.gz.fai
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions.fasta.gz.gzi
GCA_000001405.15_GRCh38_GRC_exclusions_T2Tv2.bed
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusionsv2.fasta.gz  
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusionsv2.fasta.gz.fai
GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusionsv2.fasta.gz.gzi  
GRCh38_masked_v2_decoy_gene.fasta.gz
GRCh38_masked_v2_decoy_gene.fasta.gz.fai  
GRCh38_masked_v2_decoy_gene.fasta.gz.gzi  
GRCh38_masked_v2_decoy_excludes_GPRIN2_DUSP22_FANCD2.fasta.gz
GRCh38_masked_v2_decoy_excludes_GPRIN2_DUSP22_FANCD2.fasta.gz.fai
GRCh38_masked_v2_decoy_excludes_GPRIN2_DUSP22_FANCD2.fasta.gz.gzi
GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz
GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz.fai
GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz.gzi


File Types:

* fa.gz.fai/fasta.gz.fai: index for bgzipped indexed fasta file
* fa.gz/fasta.gz: bgzipped fasta file 
* fasta.gz.gzi: This index format is a binary file listing pairs of compressed and uncompressed offsets in a BGZF file. Each compressed offset points to the start of a BGZF block. The uncompressed offset is the corresponding location in the uncompressed data stream
* bed: bed file for masking false duplications in the reference
* txt: README file
* checksum.md5: md5sum for each file

---------------------------
METHODOLOGICAL INFORMATION
---------------------------

This directory contains the reference genomes that the Genome in a Bottle 
Consortium has generally used for mapping reads. The preferred references 
have changed over time, and for different applications you may want to use 
different references. GIAB selected reference genomes in part based on a 
helpful 2017 blog post by Heng Li, which has a good discussion of reference 
genomes and issues with certain references at 
https://lh3.github.io/2017/11/13/which-human-reference-genome-to-use. 

While written in 2017, most information is still applicable in 2021, though 
there are some new variant callers that can use alternate loci, such as 
short read graph-based methods in the precisionFDA Challenge V2 
(https://doi.org/10.1101/2020.11.13.380741).


GRCh37 (aka hg19):
------------------

For GRCh37 (aka hg19), GIAB generally uses the GRCh37 reference without ALT
loci but with the hs37d5 decoy sequence from the 1000 Genomes Phase 2 Project
(hs37d5.fa.gz), because these decoy sequences contain extra sequences that 
reduce false positives resulting from mis-mapping reads from common sequences 
that are not included in GRCh37 (e.g., in the medically relevant gene KMT2C).  

However, it is important to understand that the decoy can also cause a small 
number of false negative variant calls (e.g., in the medically relevant gene 
CYP4F12). GIAB's medically relevant gene benchmark can help identify these 
limitations.  

The original source of GIAB's preferred reference for GRCh37 is at: ftp://ftp.
1000genomes.ebi.ac.uk/vol1/ftp/technical/reference/
phase2_reference_assembly_sequence/hs37d5.fa.gz


GRCh38 (hg38):
--------------

For GRCh38 (aka hg38), GIAB generally uses a masked GRCh38 reference with no 
ALT loci nor hs38d1 decoy sequences.  We do not use ALT loci because there 
are currently no ALT-aware mappers for long reads, and we currently represent 
all variants with respect to the primary reference. We do not include the 
hs38d1 decoy because it has minimal effect and includes some alternate loci 
that are not compatible with long read mappers. 

In 2021, the GIAB worked with the GRC to demonstrate improved performance 
when masking falsely duplicated regions on chr21 in GRCh38. Masking these 
false duplications dramatically improves performance in several chr21 
regions, which contain some medically relevant genes (e.g., CBS, CRYAA, and 
KCNE1).  To create the masked reference, we started with the GRCh38 reference 
with no ALT loci nor decoy from 
ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz. 

Our GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz is the same as the 
GRC one, except it is compressed with htslib bgzip to enable indexing. 
To generate the v1 masked GRCh38, we ran the Bedtools tools (https://github.com/arq5x/bedtools2) command:

```
maskFastaFromBed \
  -fi GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta \
  -bed GCA_000001405.15_GRCh38_GRC_exclusions.bed \
  -fo GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions.fasta
```

This uses the GRC bed file to mask false duplications downloaded from:
https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed

To generate the v2 masked GRCh38, we ran the Bedtools tools (https://github.com/arq5x/bedtools2) command:

```
maskFastaFromBed \
  -fi GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta \
  -bed GCA_000001405.15_GRCh38_GRC_exclusions_T2Tv2.bed \
  -fo GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions_v2.fasta
```

This uses the a bed file generated by the Telomere to Telomere Consortium Variants team to mask false duplications located in this folder `GCA_000001405.15_GRCh38_GRC_exclusionsv2.bed`.

In 2022, the GIAB worked on fixing the falsely duplicated and falsely collapsed
regions in the GRCh38 reference by masking the false duplication regions and 
adding decoys for the regions that are collapsed to other regions. We provide 
following modified GRCh38 reference (used for analysis in this paper https://doi.org/10.1186/s13059-023-02863-7). 

`GRCh38_masked_v2_decoy_gene.fasta.gz`

We provide an additional reference that excludes decoys from the above fasta as 
these decoys increase false negatives in FANCD2, GPRIN2, and DUSP22 due to 
reduced mapping quality and possible structural errors in GRCh38 or 
structural variation.

`GRCh38_masked_v2_decoy_excludes_GPRIN2_DUSP22_FANCD2.fasta.gz`


In 2023, we further refined the GRCh38 reference:

Full name: `GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz`  
Abbreviated name for inclusion in filenames: GRCh38-GIABv3

The refined GIABv3 GRCh38 corrects false duplication and false collapse errors 
in GRCh38 relative to T2T-CHM13 described in the [FixItFelix paper](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-023-02863-7). 
The false duplications are also described in this [GRC blog post](http://genomeref.blogspot.com/2021/07/one-of-these-things-doest-belong.html).  
We have masked the GRC-identified GRCh38 false duplications and added decoy sequences 
for collapsed genic regions identified in the FixItFelix paper.  The result is 
very similar to the FixItFelix modified reference with the reduced decoy set, 
but GIABv3 uses the final boundaries of false duplications recommended by GRC, 
as well as non-human contaminating sequence. Further, non-ACTGN contained in the 
reference are hard masked as Ns. Like the other GIAB GRCh38 references, we start 
with the `GCA_000001405.15_GRCh38_no_alt_analysis_set` reference that does not 
include ALT loci or the GRCh38d1 decoy.  Information on how this reference was
generated can be found here, https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/GRCh38/GRCh38_reference_update_to_GIABv3.ipynb

---------------------
NIST Data Use Policy
---------------------


This data/work was created by employees of the National Institute of Standards
and Technology (NIST), an agency of the Federal Government. Pursuant to title 17
United States Code Section 105, works of NIST employees are not subject to
copyright protection in the United States.  This data/work may be subject to
foreign copyright.


The data/work is provided by NIST as a public service and is expressly provided
“AS IS.” NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED OR STATUTORY,
INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. NIST does
not warrant or make any representations regarding the use of the data or the
results thereof, including but not limited to the correctness, accuracy,
reliability or usefulness of the data. NIST SHALL NOT BE LIABLE AND YOU HEREBY
RELEASE NIST FROM LIABILITY FOR ANY INDIRECT, CONSEQUENTIAL, SPECIAL, OR
INCIDENTAL DAMAGES (INCLUDING DAMAGES FOR LOSS OF BUSINESS PROFITS, BUSINESS
INTERRUPTION, LOSS OF BUSINESS INFORMATION, AND THE LIKE), WHETHER ARISING IN
TORT, CONTRACT, OR OTHERWISE, ARISING FROM OR RELATING TO THE DATA (OR THE USE
OF OR INABILITY TO USE THIS DATA), EVEN IF NIST HAS BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES.


To the extent that NIST may hold copyright in countries other than the United
States, you are hereby granted the non-exclusive irrevocable and unconditional
right to print, publish, prepare derivative works and distribute the NIST data,
in any medium, or authorize others to do so on your behalf, on a royalty-free
basis throughout the world.


You may improve, modify, and create derivative works of the data or any portion
of the data, and you may copy and distribute such modifications or works.
Modified works should carry a notice stating that you changed the data and
should note the date and nature of any such change. Please explicitly
acknowledge the National Institute of Standards and Technology as the source of
the data:
Data citation recommendations are provided at https://www.nist.gov/open/license.


Permission to use this data is contingent upon your acceptance of the terms of
this agreement and upon your providing appropriate acknowledgments of NIST’s
creation of the data/work.