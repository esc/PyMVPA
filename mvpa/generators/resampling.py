# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Generators for dataset resampling."""

__docformat__ = 'restructuredtext'

import random

import numpy as np

from mvpa.base.node import Node
from mvpa.base.dochelpers import _str, _repr
from mvpa.misc.support import get_limit_filter, get_nelements_per_value


class Balancer(Node):
    """Generator to (repeatedly) select subsets of a dataset.

    The Balancer can equalize the number of samples/features in a dataset, or
    select an absolute number or fraction of all available data. Selection is
    performed given a particular attribute and additionally can be limited to
    a subset of the dataset defined by more complex criteria (see ``limit``
    argument). The node can either "mark" elements as selected by adding a
    corresponding attribute to the output dataset, or actually apply the
    selection by returning a new dataset with only selected elements.
    """
    def __init__(self,
                 amount='equal',
                 attr='targets',
                 count=1,
                 limit='chunks',
                 apply_selection=False,
                 space='balanced_set',
                 **kwargs):
        """
        Parameters
        ----------
        amount : {'equal'} or int or float
          Specify the amount of elements to be selected (within the current
          ``limit``). The amount can be given as an integer value corresponding
          to the absolute number of elements per unique attribute (see ``attr``)
          value, as a float corresponding to the fraction of elements, or with
          the keyword 'equal'. In the latter case the number of to be selected
          elements is determined by the least number of available elements for
          any given unique attribute value within the current limit.
        attr : str
          Dataset attribute whose unique values define element classes that are
          to be balanced in number.
        count : int
          How many iterations to perform on ``generate()``.
        limit : None or str or dict
          If ``None`` the whole dataset is considered as one. If an single
          attribute name is given, its unique values will be used to define
          chunks of data that are balanced individually. Finally, if a
          dictionary is provided, its keys define attribute names and its values
          (single value or sequence thereof) attribute value, where all
          key-value combinations across all given items define a "selection" of
          to-be-balanced samples or features.
        apply_selection : bool
          Flag whether the balanced selection shall be applied, i.e. the output
          dataset only contains selected elements. If False, the selection is
          instead added as an attribute that merely marks selected elements (see
          ``space`` argument).
        space : str
          Name of the selection marker attribute in the output dataset that is
          created if the balanced selection is not applied to the output dataset
          (see ``apply_selection`` argument).
        """
        Node.__init__(self, space=space, **kwargs)
        self._amount = amount
        self._attr = attr
        self.nruns = count
        self._limit = limit
        self._limit_filter = None
        self._apply_selection = apply_selection


    def _call(self, ds):
        # local binding
        amount = self._amount
        attr, collection = ds.get_attr(self._attr)

        # get filter if not set already (maybe from generate())
        if self._limit_filter is None:
            limit_filter = get_limit_filter(self._limit, collection)
        else:
            limit_filter = self._limit_filter

        # ids of elements that are part of the balanced set
        balanced_set = []
        # for each chunk in the filter (might be just the selected ones)
        for limit_value in np.unique(limit_filter):
            if limit_filter.dtype == np.bool:
                # simple boolean filter -> do nothing on False
                if not limit_value:
                    continue
                # otherwise get indices of "selected ones"
                limit_idx = limit_filter.nonzero()[0]
            else:
                # non-boolean limiter -> determine "chunk" and balance within
                limit_idx = (limit_filter == limit_value).nonzero()[0]

            # apply the current limit to the target attribute
            # need list to index properly
            attr_limited = attr[list(limit_idx)]
            uattr_limited = np.unique(attr_limited)

            # handle all types of supported arguments
            if amount == 'equal':
                # go for maximum possible number of samples provided
                # by each label in this dataset
                # determine the min number of samples per class
                epa = get_nelements_per_value(attr_limited)
                min_epa = min(epa.values())
                for k in epa:
                    epa[k] = min_epa
            elif isinstance(amount, float):
                epa = get_nelements_per_value(attr_limited)
                for k in epa:
                    epa[k] = int(round(epa[k] * amount))
            elif isinstance(amount, int):
                epa = dict(zip(uattr_limited, [amount] * len(uattr_limited)))
            else:
                raise ValueError("Unknown type of amount argument '%s'" % amount)

            # select determined number of elements per unique attribute value
            selected = []
            for ua in uattr_limited:
                selected += random.sample((attr_limited == ua).nonzero()[0],
                                          epa[ua])

            # determine the final indices of selected elements and store
            # as part of the balanced set
            balanced_set += list(limit_idx[selected])

        # make full-sized boolean selection attribute and put it into
        # the right collection of the output dataset
        battr = np.zeros(len(attr), dtype=np.bool)
        battr[balanced_set] = True

        if self._apply_selection:
            if collection is ds.sa:
                return ds[battr]
            elif collection is ds.fa:
                return ds[:, battr]
            else:
                # paranoid
                raise RuntimeError(
                        "Don't know where this collection comes from. "
                        "This should never happen!")
        else:
            # shallow copy of the dataset for output
            out = ds.copy(deep=False)
            if collection is ds.sa:
                out.sa[self.get_space()] = battr
            elif collection is ds.fa:
                out.fa[self.get_space()] = battr
            else:
                # paranoid
                raise RuntimeError(
                        "Don't know where this collection comes from. "
                        "This should never happen!")
            return out


    def generate(self, ds):
        """Generate the desired number of balanced datasets datasets."""
        # figure out filter for all runs at once
        attr, collection = ds.get_attr(self._attr)
        self._limit_filter = get_limit_filter(self._limit, collection)
        # permute as often as requested
        for i in xrange(self.nruns):
            yield self(ds)

        # reset filter to do the right thing upon next call to object
        self._limit_filter = None


    def __str__(self):
        return _str(self, self._amount, n=self._attr, count=self.nruns,
                    apply_selection=self._apply_selection)
