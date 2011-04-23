'''
Routines to set up a minion
'''
# This module still needs package support, so that the functions dict returned
# can send back functions like: foo.bar.baz

# Import python libs
import os
import sys
import imp
import distutils.sysconfig

# Import cython
import pyximport
pyximport.install()

def minion_mods(opts):
    '''
    Returns the minion modules
    '''
    module_dirs = [
        os.path.join(distutils.sysconfig.get_python_lib(), 'salt/modules'),
        ] + opts['module_dirs']
    load = Loader(module_dirs, opts)
    return load.apply_introspection(load.gen_functions())

def returners(opts):
    '''
    Returns the returner modules
    '''
    module_dirs = [
        os.path.join(distutils.sysconfig.get_python_lib(), 'salt/returners'),
        ] + opts['returner_dirs']
    load = Loader(module_dirs, opts)
    return load.filter_func('returner')

def call(fun, arg=[], dirs=[]):
    '''
    Directly call a function inside a loader directory
    '''
    module_dirs = [
        os.path.join(distutils.sysconfig.get_python_lib(), 'salt/modules'),
        ] + dirs
    load = Loader(module_dirs)
    return load.call(fun, args)


class Loader(object):
    '''
    Used to load in arbitrairy modules from a directory, the Loader can also be
    used to only load specific functions from a directory, or to call modules
    in an arbitrairy directory directly.
    '''
    def __init__(self, module_dirs, opts={}):
        self.module_dirs = module_dirs
        self.opts = self.__prep_mod_opts(opts)

    def __prep_mod_opts(self, opts):
        '''
        Strip out of the opts any logger instance
        '''
        mod_opts = {}
        for key, val in opts.items():
            if key == 'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def get_docs(self, funcs, module=''):
        '''
        Return a dict containing all of the doc strings in the functions dict
        '''
        docs = {}
        for fun in funcs:
            if fun.startswith(module):
                docs[fun] = funcs[fun].__doc__
        return docs

    def call(self, fun, arg=[]):
        '''
        Call a function in the load path.
        '''
        name = fun[:fun.rindex('.')]
        try:
            fn_, path, desc = imp.find_module(name, self.module_dirs)
            mod = imp.load_module(name, fn_, path, desc)
        except ImportError:
            # The module was not found, try to find a cython module
            for mod_dir in self.module_dirs:
                for fn_ in os.listdir(mod_dir):
                    if name == fn_[:fn_.rindex('.')]:
                        # Found it, load the mod and break the loop
                        mod = pyximport.load_module(name, names[name], '/tmp')
                        return getattr(mod, fun[fun.rindex('.'):])(*arg)

        return getattr(mod, fun[fun.rindex('.') + 1:])(*arg)

    def gen_functions(self):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
        names = {}
        modules = []
        funcs = {}
        for mod_dir in self.module_dirs:
            for fn_ in os.listdir(mod_dir):
                if fn_.startswith('_'):
                    continue
                if fn_.endswith('.py')\
                    or fn_.endswith('.pyc')\
                    or fn_.endswith('.pyo')\
                    or fn_.endswith('.so')\
                    or fn_.endswith('.pyx'):
                    names[fn_[:fn_.rindex('.')]] = os.path.join(mod_dir, fn_)
        for name in names:
            try:
                if names[name].endswith('.pyx'):
                    mod = pyximport.load_module(name, names[name], '/tmp')
                else:
                    fn_, path, desc = imp.find_module(name, self.module_dirs)
                    mod = imp.load_module(name, fn_, path, desc)
            except ImportError:
                continue
            modules.append(mod)
        for mod in modules:
            if hasattr(mod, '__opts__'):
                mod.__opts__.update(self.opts)
            else:
                mod.__opts__ = self.opts

            for attr in dir(mod):
                if attr.startswith('_'):
                    continue
                if callable(getattr(mod, attr)):
                    funcs[mod.__name__ + '.' + attr] = getattr(mod, attr)
        return funcs

    def apply_introspection(self, funcs):
        '''
        Pass in a function object returned from get_functions to load in
        introspection functions.
        '''
        funcs['sys.list_functions'] = lambda: self.list_funcs(funcs)
        funcs['sys.list_modules'] = lambda: funcs.keys
        funcs['sys.doc'] = lambda module = '': self.get_docs(funcs, module)
        #funcs['sys.reload_functions'] = self.reload_functions
        return funcs

    def filter_func(self, name):
        '''
        Filter a specific function out of the functions, this is used to load
        the returners for the salt minion
        '''
        funcs = {}
        for key, fun in self.gen_functions().items():
            if key[key.index('.') + 1:] == name:
                funcs[key[:key.index('.')]] = fun
        return funcs
