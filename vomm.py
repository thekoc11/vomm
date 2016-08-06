"""This is a module for implementing variable order markov model
algorithms as described in the paper "On Prediction Using Variable
Order Markov Models" by Ron Begleiter, Ran El-Yaniv, and Golan Yona in
the Journal of Artificial Intelligence Research 22 (2004) 385-421.  """

import numpy as np

def find_contexts(training_data, d= 4):
    """
    Takes a sequence of observed symbols and finds all contexts of
    length at most d.

    training_data represents the sequence of observed symbols as a
    tuple of integers x where 0 <= x < alphabet size.

    Contexts of length k are represented as tuples of integers of length k.

    This function returns the observed contexts as a set.
    """

    contexts = set()

    N = len(training_data)

    for k in range(1,d+1):
        contexts = contexts.union([training_data[t:t+k] for t in range(N-k+1)])

    return contexts

def count_occurrences(training_data, d=4, alphabet_size = None):
    """
    Counts the number of occurrences of s\sigma where s is a context
    and \sigma is the symbol that immediately follows s in the
    training data.

    training_data represents the sequence of observed symbols as a
    tuple of integers x where 0 <= x < alphabet size.

    d determines the longest context to consider.

    alphabet_size determines the number of possible observable
    distinct symbols. If not set, the function determines it from the
    training data.

    The function returns the counts as a dictionary with key context s
    and value the counts array.

    """

    contexts = find_contexts(training_data, d = d)

    if alphabet_size == None:
        alphabet_size = max(training_data) + 1

    counts = dict([(x, np.zeros(alphabet_size,dtype=np.int)) for x in contexts])

    # Include the null context as well.
    counts[()] = np.bincount(training_data,minlength = alphabet_size)

    N = len(training_data)
    for k in range(1,d+1):
        for t in range(N-k):
            s = training_data[t:t+k]
            sigma = training_data[t+k]
            counts[s][sigma]  += 1

    return counts

def compute_ppm_probability(counts):
    """
    Takes the counts dictionary and generates the Pr(sigma| s)
    probabilities recursively. It returns a dictionary whose key is
    context and value is the probability distribution on the successive symbol.
    """

    # figure out d and alphabet_size from the counts dictionary.
    d = max( [len(x) for x in counts.keys() ])
    alphabet_size = counts[()].shape[0]

    pdf = dict([(x, np.zeros(alphabet_size)) for x in counts.keys()])

    # partition the contexts by size.
    byk = [ [] for k in range(d+1) ]
    for x in counts.keys():
        byk[len(x)].append(x)

    # Now recursively define pdfs starting with the shortest context
    # to the largest.

    pdf[()] = (counts[()] +1.0)/(counts[()].sum() + alphabet_size)

    for k in range(1,d+1):
        for x in byk[k]:
            sigma_observed = np.argwhere(counts[x] > 0).reshape(-1)
            alphabet_obs_size = len(sigma_observed)
            sigma_escaped = np.argwhere(counts[x] == 0).reshape(-1)
            denominator = alphabet_obs_size + counts[x].sum()
            x_1 = x[1:] # sub context if needed.

            if alphabet_obs_size > 0:
                escape_factor = alphabet_obs_size*1.0/denominator
            else:
                escape_factor = 1.0

            pdf[x][sigma_observed] = counts[x][sigma_observed]*1.0/denominator

            if len(sigma_escaped) > 0:
                pdf[x][sigma_escaped] = escape_factor*pdf[x_1][sigma_escaped]/pdf[x_1][sigma_escaped].sum()

            # Normalize (needed in the case that all symbols are observed)
            pdf[x] = pdf[x]/pdf[x].sum()

    return pdf

def find_largest_context(chunk,fast_lookup_table,d):
    """Find the largest context that matches the observed chunk of symbols
    and returns it.

    chunk is a sequence of symbols represented as a tuple of integers 0 <= x < alphabet size.

    fast_lookup_table is a dictionary with key context s and value the
    list of contexts which are of the form xs.

    d is the size of the largest context in the set of contexts.
    """

    if len(chunk) == 0:
        return ()

    current_context = ()
    end = len(chunk)
    start = end

    while chunk[start:end] == current_context:
        start -= 1
        if start < 0 or start < end - d:
            break

        if chunk[start:end] in fast_lookup_table[current_context]:
            current_context = chunk[start:end]
        else:
            break

    return current_context

class ppm:
    """ This class implements the "predict by partial match" algorithm. """

    def __init__(self):
        """ Not much to do here. """

    def generate_fast_lookup(self):
        """Takes the pdf_dict dictionary and computes a faster lookup
        dictionary mapping suffix s to its longer contexts xs.  I need
        this to speed up computing the probability of logpdf for an
        observed sequence
        """

        # I want to create a fast look up of context s -> xs
        # So scoring a sequence is faster.

        context_by_length  = dict([(k,[]) for k in range(self.d+1) ])

        for x in self.pdf_dict.keys():
            context_by_length[len(x)].append(x)

        # Now lets generate a dictionary look up context s -> possible context xs.
        self.context_child = {}

        for k in range(self.d):
            for x in context_by_length[k]:
                self.context_child[x] = [ y for y in context_by_length[k+1] if y[1:] == x ]

        for x in context_by_length[self.d]:
            self.context_child[x] = []

    def fit(self,training_data, d=4, alphabet_size = None):
        """
        This is the method to call to fit the model to the data.
        training_data should be a sequence of symbols represented by
        integers 0 <= x < alphabet size.

        d specifies the largest context sequence we're willing to consider.

        alphabet_size specifies the number of distinct symbols that
        can be possibly observed. If not specified, the alphabet_size
        will be inferred from the training data.
        """

        if alphabet_size == None:
            alphabet_size = max(training_data) + 1

        self.alphabet_size = alphabet_size
        self.d = d

        counts = count_occurrences(tuple(training_data),d=self.d,
                                   alphabet_size = self.alphabet_size)

        self.pdf_dict = compute_ppm_probability(counts)

        self.logpdf_dict = dict([(x,np.log(self.pdf_dict[x])) for x in self.pdf_dict.keys()])

        # For faster look up  when computing logpdf(observed data).
        self.generate_fast_lookup()

        return

    def logpdf(self,observed_data):
        """Call this method after using fitting the model to compute the log of
        the probability of an observed sequence of data.

        observed_data should be a sequence of symbols represented by
        integers 0 <= x < alphabet_size. """

        temp = tuple(observed_data)
        # start with the null context and work my way forward.

        logprob = 0.0
        for t in range(len(temp)):
            chunk = temp[max(t-self.d,0):t]
            sigma = temp[t]
            context = find_largest_context(chunk,self.context_child,self.d)
            logprob += self.logpdf_dict[context][sigma]

        return logprob

    def generate_data(self,length=200):
        """Generates data from the fitted model.
        length determines the length of symbols generated.

        It returns the data as an array of symbols represented as
        integers 0 <=x < alphabet_size. """

        new_data = np.zeros(length,dtype=np.int)

        for t in range(len(new_data)):
            chunk = tuple(new_data[max(t-self.d,0):t])
            context = find_largest_context(chunk,self.context_child,self.d)
            new_symbol = np.random.choice(self.alphabet_size,p=self.pdf_dict[context])
            new_data[t] = new_symbol

        return new_data

