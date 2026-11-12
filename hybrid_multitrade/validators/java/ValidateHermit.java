import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.semanticweb.HermiT.Reasoner;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.reasoner.*;

/** Calls HermiT through OWLReasoner, not through its command-line interface. */
public class ValidateHermit extends ValidateOntology {
    public static void main(String[] args) throws Exception {
        long start=System.nanoTime();
        OWLOntology o;
        if(args[0].equals("--unsatisfiable-class-control")) {
            OWLOntologyManager m=OWLManager.createOWLOntologyManager();
            o=m.createOntology(IRI.create("urn:hermit-control"));
            OWLDataFactory d=m.getOWLDataFactory();
            OWLClass a=d.getOWLClass(IRI.create("urn:hermit-control:A"));
            OWLClass b=d.getOWLClass(IRI.create("urn:hermit-control:B"));
            OWLClass c=d.getOWLClass(IRI.create("urn:hermit-control:Impossible"));
            for(OWLClass x:Arrays.asList(a,b,c))m.addAxiom(o,d.getOWLDeclarationAxiom(x));
            m.addAxiom(o,d.getOWLDisjointClassesAxiom(a,b));
            m.addAxiom(o,d.getOWLSubClassOfAxiom(c,a));
            m.addAxiom(o,d.getOWLSubClassOfAxiom(c,b));
        } else o=load(new File(args[0]));
        OWLReasoner r=null;
        Map<String,Object> result=map("input",args[0],"invocation","HermiT Java OWLReasoner API",
            "java_version",System.getProperty("java.version"),"error",null,
            "consistent",null,"unsatisfiable_named_classes",null);
        try {
            r=new Reasoner.ReasonerFactory().createReasoner(o);
            result.put("reasoner_name",r.getReasonerName());
            result.put("reasoner_version",r.getReasonerVersion().getMajor()+"."+r.getReasonerVersion().getMinor()+"."+r.getReasonerVersion().getPatch()+"."+r.getReasonerVersion().getBuild());
            result.put("classes_in_signature",o.getClassesInSignature().size());
            result.put("logical_axioms",o.getLogicalAxiomCount());
            result.put("imports_count",o.getImportsDeclarations().size());
            boolean consistent=r.isConsistent();result.put("consistent",consistent);
            if(consistent) {
                r.precomputeInferences(InferenceType.CLASS_HIERARCHY);
                List<String> unsat=new ArrayList<String>();
                for(OWLClass c:r.getUnsatisfiableClasses().getEntitiesMinusBottom())unsat.add(c.getIRI().toString());
                Collections.sort(unsat);
                result.put("unsatisfiable_named_classes",unsat);
                result.put("unsatisfiable_named_class_count",unsat.size());
                result.put("class_hierarchy_precomputed",r.isPrecomputed(InferenceType.CLASS_HIERARCHY));
            } else {
                result.put("class_satisfiability_skipped_reason","Ontology inconsistent; no class-quality counts reported");
            }
        } catch(Exception e) {
            result.put("error",e.getClass().getName()+": "+e.getMessage());
        } finally {
            if(r!=null)r.dispose();
        }
        result.put("seconds_including_load_and_reasoning",(System.nanoTime()-start)/1e9);
        Files.write(Paths.get(args[1]),(json(result)+"\n").getBytes(StandardCharsets.UTF_8));
        if(result.get("error")!=null)System.exit(1);
    }
}
