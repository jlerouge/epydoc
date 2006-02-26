"""
Plaintext output generation
"""

from epydoc.apidoc import *
import re

class PlaintextWriter:
    def write(self, api_doc):

        if isinstance(api_doc, ModuleDoc):
            return self.write_module(api_doc)
        if isinstance(api_doc, ClassDoc):
            return self.write_class(api_doc, 0)
        if isinstance(api_doc, RoutineDoc):
            return self.write_function(api_doc, 0)
        else:
            assert 0, ('%s not handled yet' % api_doc.__class__)

    def write_module(self, mod_doc):
        #for n,v in mod_doc.variables.items():
        #    print n, `v.value`, `v.value.value`
        
        # The cannonical name of the module.
        s = self.section('Module Name', 0)
        s += '    %s\n\n' % mod_doc.canonical_name

        # The module's description.
        if mod_doc.descr not in (None, '', UNKNOWN):
            s += self.section('Description', 0)
            s += mod_doc.descr.to_plaintext(None, indent=4)

        s += 'metadata: %s\n\n' % mod_doc.metadata # [xx] testing

        # List of classes in this module.
        classes = [v for v in mod_doc.sorted_variables
                   if isinstance(v.value, ClassDoc) and
                   v.is_imported in (False, UNKNOWN)]
        s += self.write_classlist(classes, 'Classes', 0)

        # List of functions in this module.
        funcs = [v for v in mod_doc.sorted_variables
                 if isinstance(v.value, FunctionDoc) and
                 v.is_imported in (False, UNKNOWN)]
        s += self.write_funclist(funcs, 'Functions', 0)
        
        # List of variables in this module
        variables = [v for v in mod_doc.sorted_variables
                     if not isinstance(v.value, (ClassDoc, FunctionDoc))]
        localvars = [v for v in variables if
                     v.is_imported in (False, UNKNOWN)]
        s += self.write_varlist(localvars, 'Variables', 0)

        impvars = [v for v in variables if
                   v.is_imported is True]
        s += self.write_varlist(impvars, 'Imported Variables', 0, False)
        
        return s

    def baselist(self, class_doc):
        if class_doc.bases is UNKNOWN:
            return '(unknown bases)'
        if len(class_doc.bases) == 0: return ''
        s = '('
        class_parent = class_doc.canonical_name.container()
        for i, base in enumerate(class_doc.bases):
            if base.canonical_name.container() == class_parent:
                s += str(base.canonical_name[-1])
            else:
                s += str(base.canonical_name)
            if i < len(class_doc.bases)-1: s += ', '
        return s+')'

    def write_class(self, class_doc, indent, name=None):
        baselist = self.baselist(class_doc)
        
        # If we're at the top level, then list the cannonical name of
        # the class; otherwise, our parent will have already printed
        # the name of the variable containing the class.
        if indent == 0:
            s = self.section('Class Name', 0)
            s += '    %s%s\n\n' % (class_doc.canonical_name, baselist)
        else:
            s = indent*4*' ' + 'class %s' % self.bold(name) + baselist+'\n'

        if indent>0: indent += 1

        # The class's description.
        if class_doc.descr not in (None, '', UNKNOWN):
            if indent == 0:
                s += self.section('Description', indent)
                s += class_doc.descr.to_plaintext(None, indent=4+4*indent)
            else:
                s += class_doc.descr.to_plaintext(None, indent=4*indent)

        # List of nested classes in this class.
        classes = [v for v in class_doc.sorted_variables
                   if isinstance(v.value, ClassDoc) and
                   v.is_imported in (False, UNKNOWN)]
        s += self.write_classlist(classes, 'Nested Classes', indent)

        # List of instance methods in this class.
        #print class_doc.sort_spec
        #print class_doc.sorted_variables
        funcs = [v for v in class_doc.sorted_variables
                 if isinstance(v.value, InstanceMethodDoc) and
                 v.is_imported in (False, UNKNOWN)]
        s += self.write_funclist(funcs, 'Methods', indent)

        # List of class methods in this class.
        funcs = [v for v in class_doc.sorted_variables
                 if isinstance(v.value, ClassMethodDoc) and
                 v.is_imported in (False, UNKNOWN)]
        s += self.write_funclist(funcs, 'Class Methods', indent)

        # List of static methods in this class.
        funcs = [v for v in class_doc.sorted_variables
                 if isinstance(v.value, StaticMethodDoc) and
                 v.is_imported in (False, UNKNOWN)]
        s += self.write_funclist(funcs, 'Static Methods', indent)

        # List of variables in this class
        variables = [v for v in class_doc.sorted_variables
                     if not isinstance(v.value,
                                       (ClassDoc, InstanceMethodDoc,
                                        ClassMethodDoc, StaticMethodDoc))
                     and v.is_imported in (False, UNKNOWN)]
        instvars = [v for v in variables if
                    v.is_instvar in (UNKNOWN, True)]
        s += self.write_varlist(instvars, 'Instance Variables', indent)
        classvars = [v for v in variables if
                     v.is_instvar is False]
        s += self.write_varlist(classvars, 'Class Variables', indent)

        if indent > 0:
            s = self.drawline(s, indent*4-3)
            
        return s+'\n'

    def write_variable(self, var_doc, indent):
        s = '%s%s' % ('    '*indent, self.bold(var_doc.name))
        if (var_doc.value not in (UNKNOWN, None) and
            var_doc.is_alias is True and var_doc.value.__class__ != ValueDoc):
            s += ' = %s' % var_doc.value.canonical_name
        elif (var_doc.value not in (UNKNOWN, None) and
              var_doc.value.repr is not UNKNOWN):
            if '\n' in var_doc.value.repr:
                s += ' = %s...' % var_doc.value.repr.split('\n')[0]
            else:
                s += ' = %s' % var_doc.value.repr
        if (var_doc.value not in (UNKNOWN, None) and
            var_doc.value.imported_from is True):
            s += ' (imported from %s)' % var_doc.value.imported_from
        if (len(s)-len(var_doc.name)*2) > 75:
            s = s[:72+len(var_doc.name)*2]+'...'
        s += '\n'
        if var_doc.descr not in (None, '', UNKNOWN):
            s += var_doc.descr.to_plaintext(None, indent=4+4*indent).rstrip()
        return s.rstrip()+'\n'

    def write_function(self, func_doc, indent, name=None):
        if name is None: name = func_doc.canonical_name
        s = self.signature(name, func_doc, indent)
        if func_doc.descr not in (None, '', UNKNOWN):
            s += func_doc.descr.to_plaintext(None, indent=4+4*indent)
            
        if func_doc.return_descr not in (None, '', UNKNOWN):
            s += self.section('Returns:', indent+1)
            s += func_doc.return_descr.to_plaintext(None, indent=8+4*indent)

        if func_doc.return_type not in (None, '', UNKNOWN):
            s += self.section('Return Type:', indent+1)
            s += func_doc.return_type.to_plaintext(None, indent=8+4*indent)
            
        return s.rstrip()+'\n\n'

    def signature(self, name, func_doc, indent):
        args = [self.write_arg(argname, default) for (argname, default) 
                in zip(func_doc.posargs, func_doc.posarg_defaults)]
        if func_doc.vararg: args.append('*'+func_doc.vararg)
        if func_doc.kwarg: args.append('**'+func_doc.kwarg)

        s = '%s%s(' % ('    '*indent, self.bold(str(name)))
        left = indent*4+len(name)+1
        x = left
        for i, arg in enumerate(args):
            if x > left and x+len(arg) > 75:
                s += '\n'+' '*left
                x = left
            s += arg
            x += len(arg)
            if i < len(args)-1:
                s += ', '
                x += 2
        return s+')\n'

    def write_arg(self, name, default):
        if default is None:
            return name
        elif default.repr is not UNKNOWN:
            return '%s=%s' % (name, default.repr)
        else:
            return '%s=??' % name

    def write_varlist(self, vardocs, title, indent, doublespace=True):
        s = ''
        for var_doc in vardocs:
            s += self.write_variable(var_doc, indent+1)
            if doublespace: s += '\n'
        if not s: return s
        else: return self.section(title, indent)+s

    def write_classlist(self, vardocs, title, indent):
        s = ''
        for var_doc in vardocs:
            s += self.write_class(var_doc.value, indent+1,
                                   var_doc.name)
        if not s: return s
        else: return self.section(title, indent)+s

    def write_funclist(self, vardocs, title, indent):
        s = ''
        for var_doc in vardocs:
            s += self.write_function(var_doc.value, indent+1,
                                      var_doc.name)
        if not s: return s
        else: return self.section(title, indent)+s

    def drawline(self, s, x):
        s = re.sub(r'(?m)^(.{%s}) ' % x, r'\1|', s)
        return re.sub(r'(?m)^( {,%s})$(?=\n)' % x, x*' '+'|', s)

        
    #////////////////////////////////////////////////////////////
    # Helpers
    #////////////////////////////////////////////////////////////
    
    def bold(self, text):
        """Write a string in bold by overstriking."""
        return ''.join([ch+'\b'+ch for ch in text])

    def title(self, text, indent):
        return ' '*indent + self.bold(text.capitalize()) + '\n\n'

    def section(self, text, indent):
        if indent == 0:
            return '    '*indent + self.bold(text.upper()) + '\n'
        else:
            return '    '*indent + self.bold(text.capitalize()) + '\n'


