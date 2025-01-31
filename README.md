# Image processing

The purpose of this module is to process a radio astronomical image in sourcefinding.py, where you can choose to either output a catalog of sources or output a mask file compatible with CASA for further data reduction. If the choice is to catalog, catalog_matching.py can match the output catalog (or any catalog created by PyBDSF) to external catalogs such as NVSS, SUMSS or FIRST, or even a user specified file. This allows one to check systematics such as the flux ratio (to check the primary beam) or the astrometric offsets.

This code makes extensive use `astropy` and uses PyBDSF and its dependencies for its sourcefinding, which can be found [here](https://github.com/lofar-astron/PyBDSF). Furthermore the [`regions`](https://github.com/astropy/regions) astropy package is utilised in order to create the CASA mask files. Make sure to install the regions package directly from git as earlier versions do not correctly export the regions to the CASA mask files!

PyBDSF requires an installation of `python-casacore`, and for it directly work on CASA images measures data is required to be somewhere on your system. As specified on the [`casacore`](https://github.com/casacore/casacore) github:

Various parts of casacore require measures data, which requires regular
updating. You can obtain the WSRT measures archive from the ASTRON FTP server:

ftp://ftp.astron.nl/outgoing/Measures/

Extract this somewhere on a permanent location on your filesystem.

## sourcefinding.py

Choose between outputting a catalog of sources or a mask file of Gaussians. Input parameters for PyBDSF are located in `bdsf_args_cat.json` and `bdsf_args_mask.json` in the `parsets` folder for cataloging and masking respectively. For example

```python sourcefinding.py catalog myimage.image -o fits kvis --plot --survey MALS```

Will perform sourcefinding on the image `myimage.image` and produce both a fits catalog and kvis annotation file. A plot will be produced showing the image and the sources as ellipses overlaid. All sources in the catalog will be given according to IAU conventions with the survey name prepended.

```
usage: sourcefinding.py [-h] [-o OUTPUT_FORMAT [OUTPUT_FORMAT ...]] [-s SIZE]
                        [--plot [PLOT]] [--spectral_index] [--survey SURVEY]
                        mode image

positional arguments:
  mode                  Purpose of the sourcefinding, choose between
                        cataloging (c) or masking (m). This choice will
                        determine the parameter file that PyBDSF will use, as
                        well as the output files.
  image                 Name of the image to perform sourcefinding on.

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_FORMAT [OUTPUT_FORMAT ...], --output_format OUTPUT_FORMAT [OUTPUT_FORMAT ...]
                        Output format of the catalog, supported formats are:
                        ds9, fits, star, kvis, ascii, csv. In case of fits,
                        ascii, ds9, and csv, additionally choose output
                        catalog as either source list (srl) or gaussian list
                        (gaul), default srl. Only a fits format source list
                        includes all available information and will be used
                        for further processing. Input can be multiple entries,
                        e.g. -o fits:srl ds9 (default = fits:srl).
  -s SIZE, --size SIZE  If masking, multiply the size of the masks by this
                        amount (default = 1.0).
  --plot [PLOT]         Plot the results of the sourcefinding as a png of the
                        image with sources overlaid, optionally provide an
                        output filename (default = do not plot the results).
  --spectral_index      Measure the spectral indices of the sources. this
                        requires the presence of a tt0 and tt1 image in the
                        same folder (default = do not measure spectral
                        indices).
  --survey SURVEY       Name of the survey to be used in source ids.
```

## source_catalogue_crusher.py

The puprose of this tool is to mark individual sources in the
catalogue not to be used. So essentailly to clean up the catalogue or
specify sources to be used in the next steps e.g. in the catalog
matching.
It also can generate a KVIS annotation file
and provide easy way to edit the Quality flag in the catalogue. The
following example will generate a KVIS annotation file.

```python sourcefinding.py --CAT_FILE=CATALOUGE.fits --KVISANNOUTPUT=CATALOUGE```



```
Options:
  -h, --help            show this help message and exit
  --CAT_FILE=CATFILE    CAT - file name e.g. CATALOUGE.fits
  --OUTPUTNAME=OUTPUTFILENAME
                        CATALOUGE outputfile name e.g. CATALOUGE.fits
  --DO_SELECT_PYBDSF_TYPE=DOSELECTTYPE
                        Select catalouges sources on type. [e.g. M or -M, this
                        would select all except M]
  --DO_SELECT_SOURCE_MAJ_DECON=DOSELECTSOURCES_MAJ_DECON
                        Select  sources on deconvolved major axis = minor axis
                        = zero
  --DO_SELECT_SOURCE_MAJ_FIT=DOSELECTEXTENDEDSOURCES
                        Select sources Major Axis FIT that is larger than the
                        Deconvolved Maj Axis, input value is sigma or -sigma
                        to exclude these source
  --DO_SELECT_SOURCE_TOTFLX_ISLANDFLX=DOSELECTONFLUXDENSITY
                        Select  sources on total flux density matching the
                        total island flux density, input value is sigma or
                        -sigma to exclude these sources
  --DO_SELECT_SOURCE_SAMEINDEX=DOSELECTONSAMEIDX
                        Select sources with the same column index, if [-] in
                        front of column name to exclude these sources
  --DO_SELECT_ON=DOSELECTON
                        Set selection based on table column [e.g. Maj]
  --DO_SELECT_OPERATION=DOSELECTONOPERATION
                        Input operation of selection [e.g. = (default), >, <]
  --DO_SELECT_VALUE=DOSELECTONVALUE
                        Input value of selection
  --KVISANNOUTPUT=KVISOUTPUTFILENAME
                        KVIS annotation outputfile name e.g. CATALOUGE.ann
  --KVISCOLOR=KVISCOLOR
                        Change COLOR of KVIS annotation [e.g. RANDOM ]
  --KVISPRINT           use the fitted values Maj,Min,PA or deconvolved values
                        DC_Maj, DC_Min, DC_PA
  --TABLECOLUMNOUTPUT=TCOLUMNOUTFILENAME
                        write table column output as ASCII to be edit by hand
  --TABLECOLUMNINPUT=TCOLUMNINFILENAME
                        read table column ASCII file.
  --DO_PRINT_INFO=DOPRTCATAINFO
                        =BASIC default, =FULL Print statistics of the
                        catalouge
  --DO_PRINT_TAB_COLUMN
                        Print some information of the catalouge
```


## catalog_matching.py

Match a PyBDSF catalog to an external catalog. Choices are between NVSS, SUMSS and FIRST, or a specified catalog file (mileage may vary for this option). Different types of plots can be made to judge the systematics in the catalog. For example

```catalog_matching.py myimage_catalog.fits NVSS --astro --flux```

Will match the catalog `myimage_catalog.fits` to an external catalog, in this case the NVSS. The matched catalog is put out, and additionally plots are produced with the astrometric and flux offsets between the sources in the image. 

Matching can also be done with a local catalog. If the name of the other catalog contains `bdsfcat`, the catalog is assumed to be one generated by these scripts as well, and will be automatically handled. If this is not the case, relevant information about the catalog, such as the names of columns and the shape of the beam must be put in the `parsets/extcat.json` file by hand in order for the file to properly handled by the script.

```
usage: catalog_matching.py [-h] [-d DPI] [--astro [ASTRO]] [--flux [FLUX]]
                           [--plot [PLOT]] [--fluxtype FLUXTYPE]
                           [--alpha ALPHA] [--output [OUTPUT]]
                           [--annotate [ANNOTATE]]
                           pointing ext_cat

positional arguments:
  pointing              Pointing catalog made by PyBDSF.
  ext_cat               External catalog to match to, choice between NVSS,
                        SUMMS, FIRST or a file. If the external catalog is a
                        PyBDSF catalog, make sure the filename has 'bdsfcat'
                        in it. If a different catalog, the parsets/extcat.json
                        file must be used to specify its details (default
                        NVSS).

optional arguments:
  -h, --help            show this help message and exit
  -d DPI, --dpi DPI     DPI of the output images (default = 300).
  --astro [ASTRO]       Plot the astrometric offset of the matches, optionally
                        provide an output filename (default = don't plot
                        astrometric offsets).
  --flux [FLUX]         Plot the flux ratios of the matches, optionally
                        provide an output filename (default = don't plot flux
                        ratio).
  --plot [PLOT]         Plot the field with the matched ellipses, optionally
                        provide an output filename (default = don't plot the
                        matched ellipses).
  --fluxtype FLUXTYPE   Whether to use Total or Peak flux for determining the
                        flux ratio (default = Total).
  --alpha ALPHA         The spectral slope to assume for calculating the flux
                        ratio, where Flux_1 = Flux_2 * (freq_1/freq_2)^-alpha
                        (default = 0.8)
  --output [OUTPUT]     Output the result of the matching into a catalog,
                        optionally provide an output filename (default = don't
                        output a catalog).
  --annotate [ANNOTATE]
                        Output the result of the matching into a kvis
                        annotation file, optionally provide an output filename
                        (default = don't output a catalog).
```

## catalog_analysis.py

Analyze a PyBDSF catalog with different metrics regularly applied to radio astronomical data, like source counts and fraction of resolved sources. For example

```python catalog_analysis.py myimage_catalog.fits -r myimage_rms.fits```

Runs the catalog analysis on `myimage_catalog.fits` and produces plots for the number counts, resolved fraction, and differential number counts. The rms image given is used to correct the differential number counts for area coverage.

```
usage: catalog_analysis.py [-h] [-r RMS_IMAGE] [-c COMP_CORR]
                           [--stacked_catalog] [--fancy] [-d DPI]
                           catalog

positional arguments:
  catalog               Pointing catalog(s) made by PyBDSF.

optional arguments:
  -h, --help            show this help message and exit
  -r RMS_IMAGE, --rms_image RMS_IMAGE
                        Specify input rms image for creating an rms coverage
                        plot. In the absence of a completeness correction
                        file, will also be used to correct for completeness.
  -c COMP_CORR, --comp_corr COMP_CORR
                        Specify input pickle file containing completeness
                        fractions for correcting differential number counts.
                        the file is assumed to contain at least the arrays of
                        flux bins, completeness fraction.
  --stacked_catalog     Indicate if catalog is built up from multiple
                        catalogs, for example with combine_catalogs script.
  --fancy               Output plots with latex font and formatting.
  -d DPI, --dpi DPI     DPI of the output images (default = 300).
```

## combine_catalogs.py

Combine a list of catalogs into one final output catalog. Resulting catalog can be fed into catalog analysis.
```
usage: combine_catalogs.py [-h] input_cats [input_cats ...] output_cat

positional arguments:
  input_cats  Pointing catalogs made by PyBDSF, to be combined.
  output_cat  Name of the full output catalog

optional arguments:
  -h, --help  show this help message and exit
```

