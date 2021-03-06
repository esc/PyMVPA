# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Unit tests for PyMVPA searchlight algorithm"""

import numpy.random as rnd

from mvpa.testing import *
from mvpa.testing.clfs import *
from mvpa.testing.datasets import *

from mvpa.datasets import Dataset
from mvpa.base import externals
from mvpa.clfs.transerror import ConfusionMatrix
from mvpa.measures.searchlight import sphere_searchlight, Searchlight
from mvpa.measures.gnbsearchlight import sphere_gnbsearchlight,\
     GNBSearchlight

from mvpa.misc.neighborhood import IndexQueryEngine, Sphere
from mvpa.generators.partition import NFoldPartitioner
from mvpa.generators.permutation import AttributePermutator
from mvpa.measures.base import CrossValidation
from mvpa.clfs.gnb import GNB


class SearchlightTests(unittest.TestCase):

    def setUp(self):
        self.dataset = datasets['3dlarge']
        # give the feature coord a more common name, matching the default of
        # the searchlight
        self.dataset.fa['voxel_indices'] = self.dataset.fa.myspace

    @sweepargs(common_variance=('True', 'False'))
    @sweepargs(do_roi=(False, True))
    @reseed_rng()
    def test_spatial_searchlight(self, common_variance=True, do_roi=False):
        """Tests both generic and GNBSearchlight
        Test of GNBSearchlight anyways requires a ground-truth
        comparison to the generic version, so we are doing sweepargs here
        """
        # compute N-1 cross-validation for each sphere
        # YOH: unfortunately sample_clf_lin is not guaranteed
        #      to provide exactly the same results due to inherent
        #      iterative process.  Therefore lets use something quick
        #      and pure Python
        gnb = GNB(common_variance=common_variance)
        cv = CrossValidation(gnb, NFoldPartitioner())

        ds = datasets['3dsmall'].copy()
        ds.fa['voxel_indices'] = ds.fa.myspace

        skwargs = dict(radius=1, enable_ca=['roi_sizes', 'raw_results'])

        if do_roi:
            # select some random set of features
            nroi = rnd.randint(1, ds.nfeatures)
            # and lets compute the full one as well once again so we have a reference
            # which will be excluded itself from comparisons but values will be compared
            # for selected roi_id
            sl_all = sphere_gnbsearchlight(gnb, NFoldPartitioner(cvtype=1),
                                           **skwargs)
            result_all = sl_all(ds)
            # select random features
            roi_ids = rnd.permutation(range(ds.nfeatures))[:nroi]
            skwargs['center_ids'] = roi_ids
        else:
            nroi = ds.nfeatures

        sls = [sphere_searchlight(cv, **skwargs),
               #GNBSearchlight(gnb, NFoldPartitioner(cvtype=1))
               sphere_gnbsearchlight(gnb, NFoldPartitioner(cvtype=1),
                                     indexsum='fancy', **skwargs)
               ]

        if externals.exists('scipy'):
            sls += [ sphere_gnbsearchlight(gnb, NFoldPartitioner(cvtype=1),
                                           indexsum='sparse', **skwargs)]

        # Just test nproc whenever common_variance is True
        if externals.exists('pprocess') and common_variance:
            sls += [sphere_searchlight(cv, nproc=2, **skwargs)]

        all_results = []
        for sl in sls:
            # run searchlight
            results = sl(ds)
            all_results.append(results)
            print `sl`
            # check for correct number of spheres
            self.failUnless(results.nfeatures == nroi)
            # and measures (one per xfold)
            self.failUnless(len(results) == len(ds.UC))

            # check for chance-level performance across all spheres
            # makes sense only if number of features was big enough
            # to get some stable estimate of mean
            if not do_roi or nroi > 20:
                self.failUnless(0.4 < results.samples.mean() < 0.6)

            mean_errors = results.samples.mean(axis=0)
            # that we do get different errors ;)
            self.failUnless(len(np.unique(mean_errors) > 3))

            # check resonable sphere sizes
            self.failUnless(len(sl.ca.roi_sizes) == nroi)
            if do_roi:
                # for roi we should relax conditions a bit
                self.failUnless(max(sl.ca.roi_sizes) <= 7)
                self.failUnless(min(sl.ca.roi_sizes) >= 4)
            else:
                self.failUnless(max(sl.ca.roi_sizes) == 7)
                self.failUnless(min(sl.ca.roi_sizes) == 4)

            # check base-class state
            self.failUnlessEqual(sl.ca.raw_results.nfeatures, nroi)

            # Test if we got results correctly for 'selected' roi ids
            if do_roi:
                assert_array_equal(result_all[:, roi_ids], results)



        if len(all_results) > 1:
            # if we had multiple searchlights, we can check either they all
            # gave the same result (they should have)
            aresults = np.array([a.samples for a in all_results])
            dresults = np.abs(aresults - aresults.mean(axis=0))
            dmax = np.max(dresults)
            self.failUnless(dmax <= 1e-13)


    def test_partial_searchlight_with_full_report(self):
        ds = self.dataset.copy()
        center_ids = np.zeros(ds.nfeatures, dtype='bool')
        center_ids[[3,50]] = True
        ds.fa['center_ids'] = center_ids
        # compute N-1 cross-validation for each sphere
        cv = CrossValidation(sample_clf_lin, NFoldPartitioner())
        # contruct diameter 1 (or just radius 0) searchlight
        # one time give center ids as a list, the other one takes it from the
        # dataset itself
        sls = (sphere_searchlight(cv, radius=0, center_ids=[3,50]),
               sphere_searchlight(cv, radius=0, center_ids='center_ids'))
        for sl in sls:
            # run searchlight
            results = sl(ds)
            # only two spheres but error for all CV-folds
            self.failUnlessEqual(results.shape, (len(self.dataset.UC), 2))
        # test if we graciously puke if center_ids are out of bounds
        dataset0 = ds[:, :50] # so we have no 50th feature
        self.failUnlessRaises(IndexError, sls[0], dataset0)
        # but it should be fine on the one that gets the ids from the dataset
        # itself
        results = sl(dataset0)
        assert_equal(results.nfeatures, 1)
        # check whether roi_seeds are correct
        sl = sphere_searchlight(lambda x: np.vstack((x.fa.roi_seed, x.samples)),
                                radius=1, add_center_fa=True, center_ids=[12])
        res = sl(ds)
        assert_array_equal(res.samples[1:, res.samples[0].astype('bool')].squeeze(),
                           ds.samples[:, 12])


    def test_partial_searchlight_with_confusion_matrix(self):
        ds = self.dataset
        from mvpa.clfs.stats import MCNullDist
        from mvpa.mappers.fx import mean_sample, sum_sample

        # compute N-1 cross-validation for each sphere
        cm = ConfusionMatrix(labels=ds.UT)
        cv = CrossValidation(
            sample_clf_lin, NFoldPartitioner(),
            # we have to assure that matrix does not get flatted by
            # first vstack in cv and then hstack in searchlight --
            # thus 2 leading dimensions
            # TODO: RF? make searchlight/crossval smarter?
            errorfx=lambda *a: cm(*a)[None, None,:])
        # contruct diameter 2 (or just radius 1) searchlight
        sl = sphere_searchlight(cv, radius=1, center_ids=[3, 5, 50])

        # our regular searchlight -- to compare results
        cv_gross = CrossValidation(sample_clf_lin, NFoldPartitioner())
        sl_gross = sphere_searchlight(cv_gross, radius=1, center_ids=[3, 5, 50])

        # run searchlights
        res = sl(ds)
        res_gross = sl_gross(ds)

        # only two spheres but error for all CV-folds and complete confusion matrix
        assert_equal(res.shape, (len(ds.UC), 3, len(ds.UT), len(ds.UT)))
        assert_equal(res_gross.shape, (len(ds.UC), 3))

        # briefly inspect the confusion matrices
        mat = res.samples
        # since input dataset is probably balanced (otherwise adjust
        # to be per label): sum within columns (thus axis=-2) should
        # be identical to per-class/chunk number of samples
        samples_per_classchunk = len(ds)/(len(ds.UT)*len(ds.UC))
        ok_(np.all(np.sum(mat, axis=-2) == samples_per_classchunk))
        # and if we compute accuracies manually -- they should
        # correspond to the one from sl_gross
        assert_array_almost_equal(res_gross.samples,
                           # from accuracies to errors
                           1-(mat[...,0,0] + mat[..., 1,1]).astype(float)
                           / (2*samples_per_classchunk))

        # and now for those who remained sited -- lets perform H0 MC
        # testing of this searchlight... just a silly one with minimal
        # number of permutations
        no_permutations = 10
        permutator = AttributePermutator('targets', count=no_permutations)

        # once again -- need explicit leading dimension to avoid
        # vstacking during cross-validation
        cv.postproc=lambda x: sum_sample()(x)[None,:]

        sl = sphere_searchlight(cv, radius=1, center_ids=[3, 5, 50],
                                null_dist=MCNullDist(permutator, tail='right',
                                                     enable_ca=['dist_samples']))
        res_perm = sl(ds)
        # XXX all of the res_perm, sl.ca.null_prob and
        #     sl.null_dist.ca.dist_samples carry a degenerate leading
        #     dimension which was probably due to introduced new axis
        #     above within cv.postproc
        assert_equal(res_perm.shape, (1, 3, 2, 2))
        assert_equal(sl.null_dist.ca.dist_samples.shape,
                     res_perm.shape + (no_permutations,))
        assert_equal(sl.ca.null_prob.shape, res_perm.shape)
        # just to make sure ;)
        ok_(np.all(sl.ca.null_prob.samples >= 0))
        ok_(np.all(sl.ca.null_prob.samples <= 1))

        # we should have got sums of hits across the splits
        assert_array_equal(np.sum(mat, axis=0), res_perm.samples[0])


    def test_chi_square_searchlight(self):
        # only do partial to save time

        # Can't yet do this since test_searchlight isn't yet "under nose"
        #skip_if_no_external('scipy')
        if not externals.exists('scipy'):
            return

        from mvpa.misc.stats import chisquare

        cv = CrossValidation(sample_clf_lin, NFoldPartitioner(),
                enable_ca=['stats'])


        def getconfusion(data):
            cv(data)
            return chisquare(cv.ca.stats.matrix)[0]

        sl = sphere_searchlight(getconfusion, radius=0,
                         center_ids=[3,50])

        # run searchlight
        results = sl(self.dataset)
        self.failUnless(results.nfeatures == 2)


    def test_1d_multispace_searchlight(self):
        ds = Dataset([np.arange(6)])
        ds.fa['coord1'] = np.repeat(np.arange(3), 2)
        # add a second space to the dataset
        ds.fa['coord2'] = np.tile(np.arange(2), 3)
        measure = lambda x: "+".join([str(x) for x in x.samples[0]])
        # simply select each feature once
        res = Searchlight(measure,
                          IndexQueryEngine(coord1=Sphere(0),
                                           coord2=Sphere(0)),
                          nproc=1)(ds)
        assert_array_equal(res.samples, [['0', '1', '2', '3', '4', '5']])
        res = Searchlight(measure,
                          IndexQueryEngine(coord1=Sphere(0),
                                           coord2=Sphere(1)),
                          nproc=1)(ds)
        assert_array_equal(res.samples,
                           [['0+1', '0+1', '2+3', '2+3', '4+5', '4+5']])
        res = Searchlight(measure,
                          IndexQueryEngine(coord1=Sphere(1),
                                           coord2=Sphere(0)),
                          nproc=1)(ds)
        assert_array_equal(res.samples,
                           [['0+2', '1+3', '0+2+4', '1+3+5', '2+4', '3+5']])

def suite():
    return unittest.makeSuite(SearchlightTests)


if __name__ == '__main__':
    import runner

