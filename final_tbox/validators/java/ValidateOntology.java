import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.io.RDFXMLOntologyFormat;
import org.semanticweb.owlapi.profiles.*;

/** Direct OWLAPI validation; intentionally does not instantiate any reasoner. */
public class ValidateOntology {
    static Map<String,Object> map(Object... args) {
        Map<String,Object> m = new LinkedHashMap<String,Object>();
        for (int i=0;i<args.length;i+=2) m.put((String)args[i],args[i+1]);
        return m;
    }
    static String json(Object o) {
        if (o==null) return "null";
        if (o instanceof Boolean || o instanceof Number) return o.toString();
        if (o instanceof Map) {
            List<String> items=new ArrayList<String>();
            for (Object e0:((Map<?,?>)o).entrySet()) {
                Map.Entry<?,?> e=(Map.Entry<?,?>)e0;
                items.add(json(e.getKey().toString())+":"+json(e.getValue()));
            }
            return "{"+String.join(",",items)+"}";
        }
        if (o instanceof Collection) {
            List<String> items=new ArrayList<String>();
            for(Object v:(Collection<?>)o)items.add(json(v));
            return "["+String.join(",",items)+"]";
        }
        String s=o.toString(); StringBuilder b=new StringBuilder("\"");
        for(char c:s.toCharArray()) {
            if(c=='"')b.append("\\\""); else if(c=='\\')b.append("\\\\");
            else if(c<32)b.append(String.format("\\u%04x",(int)c)); else b.append(c);
        }
        return b.append('"').toString();
    }
    static List<String> sortedStrings(Collection<?> values) {
        List<String> result=new ArrayList<String>();
        for(Object v:values)result.add(v.toString());
        Collections.sort(result); return result;
    }
    static Map<String,Object> profile(OWLOntology o) {
        OWLProfileReport r=new OWL2DLProfile().checkOntology(o);
        List<Map<String,Object>> violations=new ArrayList<Map<String,Object>>();
        for(OWLProfileViolation v:r.getViolations())violations.add(map(
            "type",v.getClass().getSimpleName(),"message",v.toString(),
            "axiom",v.getAxiom()==null?null:v.getAxiom().toString()));
        Collections.sort(violations, new Comparator<Map<String,Object>>() {
            public int compare(Map<String,Object> a,Map<String,Object>b) {
                return a.get("message").toString().compareTo(b.get("message").toString());
            }
        });
        return map("profile","OWL 2 DL","in_profile",r.isInProfile(),
                   "violation_count",violations.size(),"violations",violations);
    }
    static Map<String,Object> compare(OWLOntology a,OWLOntology b) {
        Set<OWLAxiom> lost=new HashSet<OWLAxiom>(a.getAxioms());lost.removeAll(b.getAxioms());
        Set<OWLAxiom> added=new HashSet<OWLAxiom>(b.getAxioms());added.removeAll(a.getAxioms());
        boolean annotations=a.getAnnotations().equals(b.getAnnotations());
        boolean imports=a.getImportsDeclarations().equals(b.getImportsDeclarations());
        boolean id=a.getOntologyID().equals(b.getOntologyID());
        boolean declarationOnly=true;
        for(OWLAxiom ax:added) if(!(ax instanceof OWLDeclarationAxiom))declarationOnly=false;
        boolean signature=a.getSignature().equals(b.getSignature());
        return map("equal_axiom_sets",lost.isEmpty()&&added.isEmpty(),
            "equal_logical_axiom_sets",a.getLogicalAxioms().equals(b.getLogicalAxioms()),
            "equal_ontology_annotations",annotations,"equal_import_declarations",imports,
            "equal_ontology_id",id,"lost_axioms",sortedStrings(lost),"added_axioms",sortedStrings(added),
            "equal_signature",signature,"additions_are_declarations_only",declarationOnly,
            "preserved_except_added_declarations",lost.isEmpty()&&declarationOnly&&signature&&annotations&&imports&&id,
            "passed",lost.isEmpty()&&added.isEmpty()&&annotations&&imports&&id);
    }
    static OWLOntology load(File f) throws Exception {
        OWLOntologyManager m=OWLManager.createOWLOntologyManager();
        m.addMissingImportListener(new MissingImportListener() {
            public void importMissing(MissingImportEvent e) {
                throw new IllegalStateException("Missing import: "+e.getImportedOntologyURI());
            }
        });
        return m.loadOntologyFromOntologyDocument(f);
    }
    static Map<String,Object> controls() throws Exception {
        OWLOntologyManager m=OWLManager.createOWLOntologyManager();
        OWLDataFactory d=m.getOWLDataFactory(); OWLOntology o=m.createOntology();
        OWLClass c=d.getOWLClass(IRI.create("urn:owlapi-control:Class"));
        m.addAxiom(o,d.getOWLDeclarationAxiom(c));
        Map<String,Object> positive=profile(o);
        OWLObjectProperty p=d.getOWLObjectProperty(IRI.create("urn:owlapi-control:property"));
        m.addAxiom(o,d.getOWLDeclarationAxiom(p));
        m.addAxiom(o,d.getOWLTransitiveObjectPropertyAxiom(p));
        m.addAxiom(o,d.getOWLAsymmetricObjectPropertyAxiom(p));
        Map<String,Object> negative=profile(o);
        return map("positive",positive,"negative_non_simple_asymmetric_property",negative,
            "passed",Boolean.TRUE.equals(positive.get("in_profile"))&&Boolean.FALSE.equals(negative.get("in_profile")));
    }
    public static void main(String[] args) throws Exception {
        File xml=new File(args[0]),ttl=new File(args[1]),roundtrip=new File(args[2]);
        OWLOntology a=load(xml),b=load(ttl);
        a.getOWLOntologyManager().saveOntology(a,new RDFXMLOntologyFormat(),IRI.create(roundtrip));
        OWLOntology c=load(roundtrip);
        Map<String,Object> serialization=map("rdfxml_loaded",true,"turtle_loaded",true,
            "rdfxml_vs_turtle",compare(a,b),"rdfxml_roundtrip",compare(a,c));
        boolean passed=Boolean.TRUE.equals(compare(a,b).get("passed"))&&Boolean.TRUE.equals(compare(a,c).get("passed"));
        serialization.put("passed",passed);
        Map<String,Object> result=map("java_version",System.getProperty("java.version"),
            "reasoner_invoked",false,"ontology_id",a.getOntologyID().toString(),
            "counts",map("axioms",a.getAxiomCount(),"logical_axioms",a.getLogicalAxiomCount(),
                "classes",a.getClassesInSignature().size(),"object_properties",a.getObjectPropertiesInSignature().size(),
                "data_properties",a.getDataPropertiesInSignature().size(),"named_individuals",a.getIndividualsInSignature().size(),
                "import_declarations",a.getImportsDeclarations().size()),
            "serialization_validation",serialization,"owl2_dl_profile",profile(a),"controls",controls());
        Files.write(Paths.get(args[3]),(json(result)+"\n").getBytes(StandardCharsets.UTF_8));
    }
}
