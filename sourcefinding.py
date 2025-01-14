#!/usr/bin/env python

import os
import sys
import json
import ast

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from argparse import ArgumentParser
from pathlib import Path

from astropy.wcs import WCS
from astropy.io import fits
from astropy import units as u
from astropy.stats import sigma_clip
from astropy.table import Table, Column
from astropy.coordinates import SkyCoord
from scipy import ndimage

from regions import EllipseSkyRegion, Regions

import bdsf
import casacore.images as pim
import helpers

def run_bdsf(image, output_dir, argfile, output_format):
    '''
    Run PyBDSF on an image

    Keyword arguments:
    image -- Name of image
    argfile -- Input json file containing arguments
               for bdsf functions
    '''
    imname = os.path.join(output_dir,os.path.basename(image).split('.')[0])

    path = Path(__file__).parent / argfile
    with open(path) as f:
        args_dict = json.load(f)

    # Fix json stupidness
    args_dict['process_image']['rms_box'] = ast.literal_eval(args_dict['process_image']['rms_box'])
    args_dict['process_image']['rms_box_bright'] = ast.literal_eval(args_dict['process_image']['rms_box_bright'])

    img = bdsf.process_image(image, **args_dict['process_image'])

    for img_type in args_dict['export_image']:
        if args_dict['export_image'][img_type]:
            img.export_image(outfile=imname+'_'+img_type+'.fits', clobber=True, img_type=img_type)

    outcat = None
    for of in output_format:
        fmt = of.lower().split(':')
        if len(fmt) == 1:
            fmt = fmt[0]
            cat_type = 'srl'
        if len(fmt) == 2:
            fmt, cat_type = fmt

        if fmt == 'ds9':
            outcatalog = imname+'_'+cat_type+'_bdsfcat.ds9.reg'
            img.write_catalog(outfile=outcatalog,
                              format=fmt,
                              catalog_type=cat_type,
                              clobber=True)
        elif fmt == 'kvis':
            outcatalog = imname+'_bdsfcat.kvis.ann'
            img.write_catalog(outfile=outcatalog,
                              format=fmt,
                              catalog_type='gaul',
                              clobber=True)
        elif fmt == 'star':
            outcatalog = imname+'_bdsfcat.star'
            img.write_catalog(outfile=outcatalog,
                              format=fmt,
                              catalog_type='gaul',
                              clobber=True)
        else:
            outcatalog = imname+'_'+cat_type+'_bdsfcat.'+fmt
            img.write_catalog(outfile=outcatalog,
                              format=fmt,
                              catalog_type=cat_type,
                              clobber=True)
            if fmt == 'fits' and cat_type == 'srl':
                outcat = outcatalog

    return outcat, img

def read_alpha(inpimage, catalog, regions):
    '''
    Determine spectral indices of the sources
    '''
    imname = os.path.join(os.path.dirname(inpimage),
                          os.path.basename(inpimage).split('.')[0])
    tt0 = pim.image(imname+'.image.tt0')
    tt0.putmask(False)
    tt0.tofits(imname+'_tt0.fits')
    tt0 = fits.open(imname+'_tt0.fits')

    tt1 = pim.image(imname+'.image.tt1')
    tt1.putmask(False)
    tt1.tofits(imname+'_tt1.fits')
    tt1 = fits.open(imname+'_tt1.fits')

    # Get WCS from header and drop freq and stoke axes
    wcs = WCS(tt0[0].header, naxis=2)
    pixel_regions = [region.to_pixel(wcs) for region in regions]

    alpha = tt1[0].data[0,0,:,:]/tt0[0].data[0,0,:,:]
    alpha = sigma_clip(alpha, sigma=3, masked=True)

    # Smooth image with NaNs
    U = alpha.filled(np.nan)
    V = U.copy()
    V[np.isnan(U)]=0
    VV = ndimage.gaussian_filter(V, sigma=5, order=0)

    W = 0*U.copy()+1
    W[np.isnan(U)]=0
    WW = ndimage.gaussian_filter(V, sigma=5, order=0)

    alpha == VV/WW
    alpha_list, alpha_err_list = helpers.measure_image_regions(pixel_regions, alpha, weight_image=tt1[0].data[0,0,:,:])

    a = Column(alpha_list, name='Spectral_index')
    b = Column(alpha_err_list, name='E_Spectral_index')
    catalog.add_columns([a,b], indexes=[10,10]) 

    # Clean up
    os.remove(imname+'_tt0.fits')
    os.remove(imname+'_tt1.fits')

    return catalog

def transform_cat(catalog, survey_name, img, argfile):
    '''
    Add names for sources in the catalog following IAU naming conventions
    '''
    header = dict([x.split(' = ') for x in catalog.meta['comments'][4:]])

    pointing_center = SkyCoord(float(header['CRVAL1'])*u.degree,
                               float(header['CRVAL2'])*u.degree)
    pointing_name = ['PT-'+header['OBJECT'].replace("'","")] * len(catalog)

    source_coord = SkyCoord([source['RA'] for source in catalog],
                            [source['DEC'] for source in catalog],
                            unit=(u.deg,u.deg))

    if survey_name:
        survey_name = survey_name.ljust(len(survey_name)+1)
    else:
        survey_name = ''

    ids = [survey_name+'J{0}{1}'.format(coord.ra.to_string(unit=u.hourangle,
                                                     sep='',
                                                     precision=0,
                                                     pad=True),
                                 coord.dec.to_string(sep='',
                                                      precision=0,
                                                      alwayssign=True,
                                                      pad=True)) for coord in source_coord]

    sep = pointing_center.separation(source_coord)
    quality_flag = [1] * len(catalog)

    # Add columns at appropriate indices
    col_a = Column(pointing_name, name='Pointing_id')
    col_b = Column(ids, name='Source_name')
    col_c = Column(sep, name='Sep_PC')
    col_d = Column(quality_flag, name='Quality_flag')
    catalog.add_columns([col_a, col_b, col_c, col_d],
                         indexes=[0,0,6,-1])

    # Update catalog meta
    catalog.meta['comments'] = catalog.meta['comments'][:2]
    catalog.meta.update(header)

    # Change NAXIS keywords so that astropy doesn't complain
    for key in ['NAXIS','NAXIS1','NAXIS2','NAXIS3','NAXIS4']:
        replacement = {key:key.replace('N','')}
        for k, v in list(catalog.meta.items()):
            catalog.meta[replacement.get(k, k)] = catalog.meta.pop(k)

    # Put beam and freq in header in case they're not already there
    catalog.meta['SF_BMAJ'] = img.beam[0]
    catalog.meta['SF_BMIN'] = img.beam[1]
    catalog.meta['SF_BPA'] = img.beam[2]
    catalog.meta['SF_TELE'] = img._telescope

    return catalog

def catalog_to_regions(catalog, ra='RA', dec='DEC', majax='Maj', minax='Min', PA='PA'):
    '''
    Convert catalog to a list of regions

    Keyword arguments:
    catalog -- Input catalog
    ra, dec, majax, minax, PA -- Column names of containing required variables
    '''
    regions = Regions([
        EllipseSkyRegion(center=SkyCoord(source[ra], source[dec], unit='deg'),
                         height=source[majax]*u.deg, width=source[minax]*u.deg,
                         angle=source[PA]*u.deg) for source in catalog])
    return regions

def write_mask(outfile, regions, size=1.0):
    """
    Write an output file containing sources to mask

    Keyword arguments:
    outfile -- Name of the output mask file (CRTF)
    regions -- Region or list of regions to write
    size -- Multiply input major and minor axes by this amount
    """
    if size != 1.0:
        for region in regions:
            region.height *= size
            region.width *= size

    print(f'Wrote mask file to {outfile}')
    regions.write(outfile, format='crtf')

def plot_sf_results(image_file, rms_image, regions, plot):
    '''
    Plot the results of the sourcefinding
    '''
    image = fits.open(image_file)
    rms = fits.open(rms_image)

    img = image[0].data[0,0,:,:]
    rms_img = rms[0].data[0,0,:,:]
    wcs = WCS(image[0].header, naxis=2)

    fig = plt.figure(figsize=(20,20))
    ax = plt.subplot(projection=wcs)
    ax.imshow(img/rms_img, origin='lower', cmap='bone', vmin=0, vmax=5)
    ax.set_xlabel('RA')
    ax.set_ylabel('DEC')

    for region in regions:
        patch = region.to_pixel(wcs).as_artist(facecolor='none', edgecolor='m', lw=0.25)
        ax.add_patch(patch)

    if plot is True:
        plt.savefig(os.path.splitext(image_file)[0]+'.png', dpi=300, bbox_inches='tight')
    else:
        plt.savefig(plot, dpi=300, bbox_inches='tight')
    plt.close()

def main():

    parser = new_argument_parser()
    args = parser.parse_args()

    inpimage = args.image
    mode = args.mode
    size = args.size
    plot = args.plot
    output_format = args.output_format
    spectral_index = args.spectral_index
    survey = args.survey

    if mode.lower() in 'cataloging':
        bdsf_args = 'parsets/bdsf_args_cat.json'
    elif mode.lower() in 'masking':
        bdsf_args = 'parsets/bdsf_args_mask.json'
    else:
        print(f'Invalid mode {mode}, please choose between c(ataloging) or m(asking)')
        sys.exit()

    output_dir = os.path.join(os.path.dirname(inpimage),
                              os.path.basename(inpimage).split('.')[0]+'_pybdsf')
    imname = os.path.join(output_dir, os.path.basename(inpimage).split('.')[0])
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    if output_format is None:
        output_format = ['fits:srl']

    outcat, img = run_bdsf(inpimage, output_dir, argfile=bdsf_args, output_format=output_format)

    if not outcat:
        print('No FITS catalog generated, no further operations are performed')
        sys.exit()

    bdsf_cat = Table.read(outcat)
    bdsf_regions = catalog_to_regions(bdsf_cat)

    if plot:
        plot_sf_results(f'{imname}_ch0.fits', f'{imname}_rms.fits', bdsf_regions, plot)

    if spectral_index:
        bdsf_cat = read_alpha(inpimage, bdsf_cat, bdsf_regions)

    # Determine output by mode
    if mode.lower() in 'cataloging':
        outcat = outcat.replace('srl_','')
        bdsf_cat = transform_cat(bdsf_cat, survey, img, bdsf_args)
        print(f'Wrote catalog to {outcat}')
        bdsf_cat.write(outcat, overwrite=True)

    if mode.lower() in 'masking':
        bdsf_cat.write(outcats[i], overwrite=True)
        write_mask(outfile=imname+'_mask.crtf', regions=bdsf_regions, size=size)

    # Make sure the log file is in the output folder
    logname = inpimage+'.pybdsf.log'
    os.system(f'mv {logname} {output_dir}')

def new_argument_parser():

    parser = ArgumentParser()

    parser.add_argument("mode",
                        help="""Purpose of the sourcefinding, choose between
                                cataloging (c) or masking (m). This choice will determine
                                the parameter file that PyBDSF will use, as well as the
                                output files.""")
    parser.add_argument("image",
                        help="""Name of the image to perform sourcefinding on.""")
    parser.add_argument("-o", "--output_format", nargs='+', default=None,
                        help="""Output format of the catalog, supported formats
                                are: ds9, fits, star, kvis, ascii, csv. In case of fits,
                                ascii, ds9, and csv, additionally choose output catalog as either
                                source list (srl) or gaussian list (gaul), default srl. Only
                                a fits format source list includes all available information and will be 
                                used for further processing. Input can be multiple entries, 
                                e.g. -o fits:srl ds9 (default = fits:srl).""")
    parser.add_argument("-s", "--size", default=1.0,
                        help="""If masking, multiply the size of the masks by this
                                amount (default = 1.0).""")
    parser.add_argument("--plot", nargs="?", const=True,
                        help="""Plot the results of the sourcefinding as a png
                                of the image with sources overlaid, optionally
                                provide an output filename (default = do
                                not plot the results).""")
    parser.add_argument("--spectral_index", action='store_true',
                        help="""Measure the spectral indices of the sources.
                                this requires the presence of a tt0 and tt1
                                image in the same folder (default = do not measure
                                spectral indices).""")
    parser.add_argument("--survey", default=None,
                        help="Name of the survey to be used in source ids.")
    return parser

if __name__ == '__main__':
    main()



# time python3 sourcefinding.py catalog ./data/Abell2256_23MHz.int.restored.fits -o fits --plot SourceFind23MHz.png
# time python3 sourcefinding.py catalog ./data/Abell2256_46MHz.int.restored.fits -o fits --plot SourceFind46MHz.png 
# time python3 sourcefinding.py catalog ./data/Abell2256_144MHz.int.restored.fits -o fits --plot SourceFind144MHz.png 
