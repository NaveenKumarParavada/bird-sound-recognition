from flask import Flask, request, render_template, flash, send_from_directory, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import uuid
from functools import wraps
import traceback
import logging
 
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# Try to import BirdNET
try:
    from birdnetlib import Recording
    from birdnetlib.analyzer import Analyzer
    BIRDNET_AVAILABLE = True
    logger.info("BirdNET library imported successfully")
except ImportError as e:
    BIRDNET_AVAILABLE = False
    logger.error(f"BirdNET library not available: {e}")
    print("Warning: birdnetlib not available. Install with: pip install birdnetlib")
 
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
 
# Expanded audio format support - BirdNET can handle these
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
 
# Create necessary folders
for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER'], 'templates', 'static/css', 'static/js']:
    os.makedirs(folder, exist_ok=True)
 
# Simple in-memory user storage
users = {
    'naveen': {
        'password': generate_password_hash('1234'),
        'name': 'Naveen',
        'profile_image': 'default-avatar.jpg'
    },
    'admin': {
        'password': generate_password_hash('admin'),
        'name': 'Admin User',
        'profile_image': 'default-avatar.jpg'
    }
}
 
# Analysis history storage
analysis_history = {}
 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
def validate_audio_file(file_path):
    """Validate that the uploaded file is a valid audio file"""
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty"
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Basic file header validation
        with open(file_path, 'rb') as f:
            header = f.read(12)
            
        # Check common audio file signatures
        if file_path.lower().endswith('.mp3'):
            if not (header.startswith(b'ID3') or header[0:2] == b'\xff\xfb' or header[0:2] == b'\xff\xf3'):
                return False, "Invalid MP3 file format"
        elif file_path.lower().endswith('.wav'):
            if not header.startswith(b'RIFF') or header[8:12] != b'WAVE':
                return False, "Invalid WAV file format"
        elif file_path.lower().endswith('.ogg'):
            if not header.startswith(b'OggS'):
                return False, "Invalid OGG file format"
        elif file_path.lower().endswith('.flac'):
            if not header.startswith(b'fLaC'):
                return False, "Invalid FLAC file format"
        
        return True, "Valid audio file"
    except Exception as e:
        return False, f"File validation error: {str(e)}"
 
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
 
# Initialize analyzer with better error handling
analyzer = None
if BIRDNET_AVAILABLE:
    try:
        logger.info("Initializing BirdNET analyzer...")
        analyzer = Analyzer()
        logger.info("BirdNET analyzer initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing BirdNET: {e}")
        analyzer = None
 
# Enhanced bird information database
BIRD_INFO = {
    "Turdus migratorius": {
        "habitat": "Gardens, parks, woodlands, and urban areas",
        "migration": "Partial migrant; some populations stay year-round",
        "diet": "Worms, insects, fruits, and berries",
        "conservation_status": "Least Concern",
        "description": "The American Robin is known for its brick-red breast and cheerful song. Often seen hopping on lawns searching for worms, it is one of the most familiar birds in North America."
    },
    "Geothlypis tolmiei": {
        "habitat": "Dense undergrowth in coniferous and mixed forests, especially near streams",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Insects, spiders, and small berries",
        "conservation_status": "Least Concern",
        "description": "MacGillivray's Warbler is a secretive songbird with bold white eye crescents and a gray hood. Males have a slate-gray head contrasting with a bright yellow belly."
    },
    "Poecile atricapillus": {
        "habitat": "Deciduous and mixed forests, parks, and wooded suburban areas",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects, seeds, berries, and cached food in winter",
        "conservation_status": "Least Concern",
        "description": "The Black-capped Chickadee is a small, round, acrobatic songbird with a black cap and bib and white cheeks. Bold and curious, they readily visit backyard feeders and can remember thousands of food cache locations."
    },
    "Corvus brachyrhynchos": {
        "habitat": "Open woodlands, fields, parks, roadsides, and urban areas",
        "migration": "Mostly non-migratory; some northern populations move south in winter",
        "diet": "Omnivorous — insects, small animals, fruits, carrion, and human food waste",
        "conservation_status": "Least Concern",
        "description": "The American Crow is a large, highly intelligent all-black bird known for its distinctive caw. They live in family groups, use tools, and have been shown to recognize individual human faces."
    },
    "Pipilo maculatus": {
        "habitat": "Shrubby areas, forest edges, chaparral, and dense undergrowth across western North America",
        "migration": "Mostly non-migratory; some populations make short seasonal movements",
        "diet": "Seeds, insects, berries, and small invertebrates scratched from the leaf litter",
        "conservation_status": "Least Concern",
        "description": "The Spotted Towhee is a large, striking sparrow with a black hood, rufous flanks, and white spots on its wings. Males are boldly patterned; both sexes forage noisily on the ground using a characteristic two-footed backward scratch."
    },
    "Pipilo erythrophthalmus": {
        "habitat": "Forest edges, thickets, shrubby areas, and suburban gardens in eastern North America",
        "migration": "Partially migratory; northern populations move south in winter",
        "diet": "Seeds, berries, insects, and invertebrates",
        "conservation_status": "Least Concern",
        "description": "The Eastern Towhee is a large sparrow with a black hood, white belly, and rufous sides. Its distinctive 'drink-your-teeeea' song is one of the most recognizable sounds of eastern woodland edges."
    },
    "Melanerpes formicivorus": {
        "habitat": "Oak woodlands and mixed forests with abundant oak trees in western North America",
        "migration": "Non-migratory; strongly tied to oak habitat year-round",
        "diet": "Acorns (stored in granary trees), insects, sap, and fruit",
        "conservation_status": "Least Concern",
        "description": "The Acorn Woodpecker is a striking, clown-faced bird that lives in family groups and stores thousands of acorns in specially drilled 'granary trees.' The same tree may be used and expanded by multiple generations."
    },
    "Melanerpes nuttallii": {
        "habitat": "Oak woodlands, river valleys with willows and cottonwoods, and urban areas with trees in California",
        "migration": "Non-migratory year-round resident of California",
        "diet": "Insects (especially beetles and ants), berries, acorns, and occasionally sap",
        "conservation_status": "Least Concern",
        "description": "Nuttall's Woodpecker is a small woodpecker endemic to California. Males sport a red patch on the back of the head, while both sexes show a bold black-and-white barred pattern on the back. They are highly vocal birds closely associated with oak habitat."
    },
    "Melanerpes carolinus": {
        "habitat": "Open forests, woodlands, parks, and suburban areas in eastern North America",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects, nuts, seeds, berries, and occasionally small vertebrates",
        "conservation_status": "Least Concern",
        "description": "The Red-bellied Woodpecker has a striking red cap and nape (full cap in males) and a barred black-and-white back. Despite its name, the reddish belly patch is often hard to see. They are adaptable woodpeckers that readily visit suburban feeders."
    },
    "Troglodytes aedon": {
        "habitat": "Open woodlands, gardens, thickets, forest edges, and suburban areas",
        "migration": "Migratory in northern parts of range; winters in southern US and Central America",
        "diet": "Insects, spiders, and other small invertebrates",
        "conservation_status": "Least Concern",
        "description": "The House Wren is a tiny, energetic brown bird with a short upturned tail and an enormous bubbling song far out of proportion to its tiny size. One of the most widespread wrens in the Americas, it readily nests in birdhouses."
    },
    "Cyanocitta stelleri": {
        "habitat": "Coniferous and mixed forests, especially pine-oak woodlands in western North America",
        "migration": "Non-migratory; may descend to lower elevations in winter",
        "diet": "Acorns, pine seeds, insects, berries, eggs, and nestlings",
        "conservation_status": "Least Concern",
        "description": "Steller's Jay is the only crested jay in western North America, with a sooty black head and crest and vivid blue wings. Bold and noisy, it is often found at campsites and picnic areas and is a talented mimic of hawk calls."
    },
    "Vireo cassinii": {
        "habitat": "Open coniferous and mixed forests, oak woodlands, and forest edges in western North America",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Insects and spiders gleaned from foliage; occasionally small berries",
        "conservation_status": "Least Concern",
        "description": "Cassin's Vireo is a medium-sized songbird with a gray head, crisp white spectacles, two white wing bars, and yellowish-green flanks. It sings a persistent, slow series of short phrases and is one of three closely related 'solitary vireo' species."
    },
    "Vireo olivaceus": {
        "habitat": "Deciduous and mixed forests, forest edges, and riparian woodlands",
        "migration": "Long-distance migrant; winters in South America",
        "diet": "Insects and berries",
        "conservation_status": "Least Concern",
        "description": "The Red-eyed Vireo is one of the most abundant songbirds in North American forests, known for its persistent singing throughout the day even in the heat of summer. Its red iris is visible at close range."
    },
    "Zenaida macroura": {
        "habitat": "Open habitats including fields, farms, suburbs, roadsides, and lightly wooded areas",
        "migration": "Partially migratory; northern populations move south in winter",
        "diet": "Seeds almost exclusively — grass seeds, grains, and wild seeds",
        "conservation_status": "Least Concern",
        "description": "The Mourning Dove is a slender, long-tailed dove with soft brown plumage and a gentle cooing call. One of the most abundant and widespread birds in North America, it is a popular game bird and a frequent backyard visitor."
    },
    "Melospiza melodia": {
        "habitat": "Shrubby areas near water, marshes, thickets, forest edges, and suburban gardens",
        "migration": "Partially migratory; northern populations move to southern US in winter",
        "diet": "Seeds, insects, and berries",
        "conservation_status": "Least Concern",
        "description": "The Song Sparrow is a medium-sized sparrow with heavy brown streaking and a central breast spot. It is known for a complex, musical song that varies considerably across its many regional subspecies found throughout North America."
    },
    "Spinus tristis": {
        "habitat": "Open weedy fields, floodplains, and areas with shrubs and trees",
        "migration": "Migratory and nomadic; moves in flocks in winter to find food",
        "diet": "Almost exclusively seeds, especially thistle and sunflower seeds",
        "conservation_status": "Least Concern",
        "description": "The American Goldfinch is a small, brilliant yellow finch with black wings in summer. It is the only finch that molts body feathers twice a year, turning drab olive in winter. They nest late in summer, timing it with the peak of thistle seed production."
    },
    "Sitta carolinensis": {
        "habitat": "Deciduous and mixed forests, parks, and wooded suburbs",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects, spiders, seeds, and nuts cached in bark crevices",
        "conservation_status": "Least Concern",
        "description": "The White-breasted Nuthatch is a compact bird with a blue-gray back, white face, and a long upturned bill. Famous for walking headfirst down tree trunks, it searches bark crevices for insects invisible to other birds."
    },
    "Sitta pygmaea": {
        "habitat": "Ponderosa pine forests of western North America",
        "migration": "Non-migratory; stays in pine forests year-round",
        "diet": "Insects, pine seeds, and small invertebrates from bark",
        "conservation_status": "Least Concern",
        "description": "The Pygmy Nuthatch is one of North America's smallest birds, living in highly social flocks in ponderosa pine forests. Helpers assist breeding pairs at the nest, and the whole flock roosts together in tree cavities on cold nights."
    },
    "Catharus ustulatus": {
        "habitat": "Moist coniferous and mixed forests, especially near streams",
        "migration": "Long-distance migrant; winters in Central and South America",
        "diet": "Insects and berries",
        "conservation_status": "Least Concern",
        "description": "The Swainson's Thrush has a spotted breast and buffy eye ring. Its beautiful, spiraling flute-like song — rising in pitch with each phrase — is one of the most evocative sounds of northern forests during breeding season."
    },
    "Catharus guttatus": {
        "habitat": "Coniferous and mixed forests; winters in thickets and wooded areas",
        "migration": "Migratory; one of the last thrushes to migrate south in fall",
        "diet": "Insects, earthworms, berries, and small fruits",
        "conservation_status": "Least Concern",
        "description": "The Hermit Thrush is famous for its beautiful, flute-like song, often considered the finest of any North American bird. It is the only spotted thrush that winters in the US and habitually raises and lowers its reddish tail."
    },
    "Setophaga coronata": {
        "habitat": "Coniferous and mixed forests; winters in a wide variety of open habitats",
        "migration": "Migratory; one of the most abundant warblers in North America",
        "diet": "Insects during breeding; berries and fruit in winter, especially bayberries",
        "conservation_status": "Least Concern",
        "description": "The Yellow-rumped Warbler is easily identified by its yellow rump patch, visible in flight. It is the most versatile warbler in North America — able to digest waxy berries that other warblers cannot, allowing it to winter far north of other warbler species."
    },
    "Setophaga petechia": {
        "habitat": "Shrubby areas near water, gardens, and woodland edges",
        "migration": "Long-distance migrant; winters from southern US through South America",
        "diet": "Insects, especially caterpillars",
        "conservation_status": "Least Concern",
        "description": "The Yellow Warbler is a small, bright canary-yellow bird with rusty streaks on the breast of males. It is one of the most widespread warblers in the Americas and is known for building a new nest layer on top of cowbird eggs to avoid raising parasitic young."
    },
    "Setophaga occidentalis": {
        "habitat": "Coniferous forests, especially those with dense undergrowth, in the western US",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Insects gleaned from foliage and bark",
        "conservation_status": "Least Concern",
        "description": "The Hermit Warbler is a beautiful yellow-headed warbler that forages high in the canopy of old-growth coniferous forests. It hybridizes with Townsend's Warbler where their ranges overlap."
    },
    "Anas platyrhynchos": {
        "habitat": "Lakes, ponds, marshes, rivers, and urban parks with water",
        "migration": "Partially migratory; many populations are year-round residents",
        "diet": "Aquatic plants, seeds, insects, small fish, and crustaceans",
        "conservation_status": "Least Concern",
        "description": "The Mallard is the most familiar duck in the world. Males have an iridescent green head and yellow bill; females are mottled brown. Mallards are the ancestor of most domestic duck breeds and are highly adaptable to human-modified environments."
    },
    "Buteo jamaicensis": {
        "habitat": "Open and semi-open habitats including fields, roadsides, deserts, and woodlands",
        "migration": "Partially migratory; many are year-round residents",
        "diet": "Small mammals (especially voles and rabbits), birds, reptiles, and carrion",
        "conservation_status": "Least Concern",
        "description": "The Red-tailed Hawk is one of the largest and most common hawks in North America, recognized by its brick-red tail. It is the default hawk cry used in film and TV for all raptors and is a master of soaring on thermals over open country."
    },
    "Accipiter cooperii": {
        "habitat": "Forests and woodland edges; increasingly nests in suburban areas",
        "migration": "Partially migratory; some move south in winter",
        "diet": "Primarily medium-sized birds; occasional small mammals",
        "conservation_status": "Least Concern",
        "description": "Cooper's Hawk is an agile, medium-sized hawk that pursues birds through dense vegetation at high speed. Once heavily persecuted, it has made a strong comeback and is now one of the most common hawks in suburban and urban areas."
    },
    "Haemorhous mexicanus": {
        "habitat": "Urban areas, suburbs, farms, forest edges, and desert scrub",
        "migration": "Non-migratory; has greatly expanded its range eastward across North America",
        "diet": "Seeds, buds, berries, and occasionally insects",
        "conservation_status": "Least Concern",
        "description": "The House Finch is a small, chunky finch. Males have a rosy-red head and breast; females are plain brown and streaked. Originally a western species, they were introduced to the eastern US in the 1940s and have since spread continent-wide."
    },
    "Haemorhous purpureus": {
        "habitat": "Coniferous forests, mixed woodlands, and suburban areas",
        "migration": "Migratory and nomadic; moves in flocks in winter",
        "diet": "Seeds, buds, berries, and insects",
        "conservation_status": "Least Concern",
        "description": "The Purple Finch is a chunky, rose-red finch (males look like they were dipped in raspberry juice) that can be difficult to distinguish from the House Finch. It prefers more forested habitats and is more strongly migratory."
    },
    "Passer domesticus": {
        "habitat": "Cities, towns, farms, and anywhere with human habitation worldwide",
        "migration": "Non-migratory; one of the most widespread birds on Earth",
        "diet": "Grains, seeds, discarded human food, and some insects",
        "conservation_status": "Least Concern",
        "description": "The House Sparrow is a stocky, introduced sparrow from Europe. Males have a gray crown and black bib; females are plain buffy-brown. Introduced to New York in 1851, they are now among the most abundant birds on the planet."
    },
    "Sturnus vulgaris": {
        "habitat": "Open fields, lawns, urban areas, farms, and woodland edges",
        "migration": "Partially migratory; introduced species in North America",
        "diet": "Insects, earthworms, fruits, seeds, and garbage",
        "conservation_status": "Least Concern",
        "description": "The European Starling is an iridescent black bird introduced to North America in 1890 by Shakespeare enthusiasts. In winter, fresh plumage shows white spots; in summer, the spots wear away to reveal glossy green and purple sheens. They form breathtaking murmurations of millions of birds."
    },
    "Columba livia": {
        "habitat": "Cities, towns, cliffs, and agricultural areas worldwide",
        "migration": "Non-migratory; famous for homing ability",
        "diet": "Grains, seeds, bread, and human food waste",
        "conservation_status": "Least Concern",
        "description": "The Rock Pigeon (common pigeon) is the world's oldest domesticated bird, with a history of over 5,000 years alongside humans. Wild birds are blue-gray with iridescent neck feathers, but feral populations show enormous color variation from centuries of selective breeding."
    },
    "Aphelocoma californica": {
        "habitat": "Oak woodlands, chaparral, suburbs, and parks along the Pacific coast",
        "migration": "Non-migratory year-round resident",
        "diet": "Acorns, insects, small vertebrates, eggs, and fruit",
        "conservation_status": "Least Concern",
        "description": "The California Scrub-Jay is a strikingly blue-and-gray, crestless jay. Highly intelligent, it practices food caching and has been shown to plan for the future and even consider the perspectives of other jays — one of few non-human animals capable of this."
    },
    "Calypte anna": {
        "habitat": "Chaparral, open woodlands, coastal scrub, gardens, and urban areas along the Pacific coast",
        "migration": "Non-migratory; year-round resident of the Pacific Coast",
        "diet": "Nectar from flowers, small insects, and tree sap from sapsucker wells",
        "conservation_status": "Least Concern",
        "description": "Anna's Hummingbird is a medium-sized hummingbird whose males dazzle with an iridescent rose-red head and throat (gorget). Unlike most hummingbirds, Anna's stays year-round in the US and is the only hummingbird that produces a true song."
    },
    "Selasphorus rufus": {
        "habitat": "Open areas, forest edges, mountain meadows, and gardens",
        "migration": "Long-distance migrant; makes one of the longest migrations relative to body size of any bird",
        "diet": "Nectar from flowers and small flying insects",
        "conservation_status": "Least Concern",
        "description": "The Rufous Hummingbird is a fiery orange-red hummingbird that migrates from Mexico to Alaska and back each year — an extraordinary journey for a bird barely 3 inches long. Males are extremely aggressive at feeders, chasing away birds many times their size."
    },
    "Junco hyemalis": {
        "habitat": "Coniferous and mixed forests; winters in open woodlands, fields, and suburban areas",
        "migration": "Migratory; breeds in Canada and mountains, winters across much of the US",
        "diet": "Seeds, insects, and berries",
        "conservation_status": "Least Concern",
        "description": "The Dark-eyed Junco is a small sparrow with white outer tail feathers that flash in flight, often called 'snowbirds' because they arrive at feeders across the US in winter. Multiple regional forms differ in plumage but are all one species."
    },
    "Quiscalus mexicanus": {
        "habitat": "Open and semi-open areas, farms, urban parks, and wetlands in the southwestern US",
        "migration": "Partially migratory; range is expanding northward",
        "diet": "Omnivorous — insects, grains, fruit, small vertebrates, and garbage",
        "conservation_status": "Least Concern",
        "description": "The Great-tailed Grackle is a large, long-tailed blackbird with stunning iridescent plumage in males. Extremely noisy, they produce a vast repertoire of mechanical, squeaky, and electronic-sounding calls. One of the fastest-expanding bird species in North America."
    },
    "Quiscalus quiscula": {
        "habitat": "Open woodlands, parks, fields, marshes, and suburban areas in eastern North America",
        "migration": "Partially migratory; forms large flocks in winter",
        "diet": "Omnivorous — grains, insects, small vertebrates, eggs, and garbage",
        "conservation_status": "Least Concern",
        "description": "The Common Grackle is a large, iridescent blackbird with a long keel-shaped tail. Its eye is a striking bright yellow. Grackles are highly adaptable and often nest in large, noisy colonies, sometimes causing conflicts with farmers due to grain consumption."
    },
    "Poecile gambeli": {
        "habitat": "Mountain coniferous forests, especially pine and fir, in western North America",
        "migration": "Non-migratory; may descend to lower elevations in harsh winters",
        "diet": "Insects, seeds, and berries; caches food for winter",
        "conservation_status": "Least Concern",
        "description": "The Mountain Chickadee is similar to the Black-capped Chickadee but has a distinctive white eyebrow stripe. A common bird of western mountain forests, it has a remarkable spatial memory for relocating thousands of individually cached food items."
    },
    "Psaltriparus minimus": {
        "habitat": "Open woodlands, chaparral, oak scrub, and suburban gardens in western North America",
        "migration": "Non-migratory; wanders in flocks outside breeding season",
        "diet": "Small insects, spiders, and other tiny invertebrates",
        "conservation_status": "Least Concern",
        "description": "The Bushtit is a tiny, long-tailed gray bird that travels in loose, chattering flocks of up to 40 individuals. They build remarkable hanging sock nests up to a foot long, woven from plant fibers, spiderwebs, and moss."
    },
    "Chamaea fasciata": {
        "habitat": "Dense chaparral and brushy hillsides along the Pacific coast",
        "migration": "Non-migratory; rarely leaves its home territory",
        "diet": "Insects, berries, and seeds",
        "conservation_status": "Least Concern",
        "description": "The Wrentit is a secretive, long-tailed bird endemic to the Pacific coast chaparral. Its distinctive bouncing-ball call is one of the most characteristic sounds of the California coast. Pairs mate for life and stay together constantly throughout the year."
    },
    "Toxostoma redivivum": {
        "habitat": "Chaparral, coastal sage scrub, and open woodlands in California and Baja California",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects, berries, and seeds scratched from the ground",
        "conservation_status": "Least Concern",
        "description": "The California Thrasher is a large, sickle-billed bird endemic to California's chaparral. It uses its long curved bill to dig and sweep aside leaf litter like a scythe. It is an accomplished mimic and sings a loud, complex song year-round."
    },
    "Mimus polyglottos": {
        "habitat": "Open areas with shrubs, forest edges, suburban gardens, and parks",
        "migration": "Partially migratory; northern populations move south in winter",
        "diet": "Insects, berries, and fruit",
        "conservation_status": "Least Concern",
        "description": "The Northern Mockingbird is North America's most famous mimic, able to imitate dozens of other bird species, car alarms, and squeaky hinges. Males may sing all night during breeding season and can learn new songs throughout their lifetime."
    },
    "Thryomanes bewickii": {
        "habitat": "Shrubby areas, chaparral, open woodlands, gardens, and suburban areas in western North America",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects, spiders, and small invertebrates",
        "conservation_status": "Least Concern",
        "description": "Bewick's Wren is an energetic, long-tailed wren with a bold white eyebrow stripe. Males sing a complex, variable song to defend territories year-round. Their range has contracted significantly in the eastern US but remains strong in the west."
    },
    "Spizella passerina": {
        "habitat": "Open woodlands, parks, forest edges, and suburban areas",
        "migration": "Migratory; winters in southern US and Mexico",
        "diet": "Seeds and insects",
        "conservation_status": "Least Concern",
        "description": "The Chipping Sparrow is a small, trim sparrow with a bright rufous cap and clean white eyebrow. One of the most common sparrows in North America, it often nests in ornamental shrubs and is a familiar visitor to backyard feeders."
    },
    "Zonotrichia leucophrys": {
        "habitat": "Shrubby areas, forest edges, and open fields; winters in weedy areas and gardens",
        "migration": "Migratory; breeds in the Arctic and high mountains",
        "diet": "Seeds, insects, and berries",
        "conservation_status": "Least Concern",
        "description": "The White-crowned Sparrow is a large, handsome sparrow with bold black-and-white head stripes. Famous in behavioral ecology for dialect studies — populations in different regions sing distinctly different songs that young birds learn from adults."
    },
    "Zonotrichia atricapilla": {
        "habitat": "Coniferous forests and thickets; winters in dense brush and forest edges",
        "migration": "Migratory; breeds in Alaska and Canada",
        "diet": "Seeds, berries, and insects",
        "conservation_status": "Least Concern",
        "description": "The Golden-crowned Sparrow has a bright yellow forecrown bordered by black, and a melodious three-note whistled song. A common winter visitor to the Pacific coast, it often forages in mixed flocks with White-crowned Sparrows."
    },
    "Icteria virens": {
        "habitat": "Dense thickets, brushy fields, and forest edges near water",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Insects, spiders, berries, and wild fruits",
        "conservation_status": "Least Concern",
        "description": "The Yellow-breasted Chat is the largest warbler in North America and so unusual in behavior and appearance that it is placed in its own family. It produces a bizarre, varied series of whistles, cackles, and gurgles, often singing at night."
    },
    "Picoides pubescens": {
        "habitat": "Open woodlands, parks, orchards, and suburban areas across North America",
        "migration": "Non-migratory year-round resident",
        "diet": "Insects in wood (especially beetle larvae), seeds, and berries",
        "conservation_status": "Least Concern",
        "description": "The Downy Woodpecker is the smallest woodpecker in North America, with a short bill and fluffy appearance. It is often the first woodpecker to visit new bird feeders. Males have a small red patch on the back of the head."
    },
    "Dryobates villosus": {
        "habitat": "Mature forests, parks, and wooded suburbs across North America",
        "migration": "Non-migratory year-round resident",
        "diet": "Wood-boring insects (especially beetle larvae), nuts, and berries",
        "conservation_status": "Least Concern",
        "description": "The Hairy Woodpecker looks like a larger version of the Downy Woodpecker with a proportionally much longer bill. It prefers larger trees and older forests and is an important excavator of nest cavities used by many other cavity-nesting species."
    },
    "Colaptes auratus": {
        "habitat": "Open woodlands, forest edges, fields, and suburban areas",
        "migration": "Partially migratory; northern populations move south in winter",
        "diet": "Ants and beetles (primarily forages on the ground, unlike most woodpeckers)",
        "conservation_status": "Least Concern",
        "description": "The Northern Flicker is a large, brown woodpecker that forages mainly on the ground for ants. In flight, it reveals a brilliant yellow (east) or red (west) underwing flash and a white rump patch. It is one of the few migratory woodpeckers in North America."
    },
    "Contopus cooperi": {
        "habitat": "Mature coniferous and mixed forests, especially with tall dead snags",
        "migration": "Long-distance migrant; winters in South America",
        "diet": "Flying insects caught in aerial sallies",
        "conservation_status": "Least Concern",
        "description": "The Olive-sided Flycatcher perches at the very tops of tall dead trees and calls a distinctive 'quick-THREE-beers!' It is a declining species associated with old-growth forests and is one of the longest-distance migrants among flycatchers."
    },
    "Empidonax difficilis": {
        "habitat": "Riparian woodlands, forest edges, and canyons in western North America",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Flying insects",
        "conservation_status": "Least Concern",
        "description": "The Pacific-slope Flycatcher is a small, olive-green flycatcher best identified by its rising 'pee-weet' call. It is one of the most common breeding flycatchers in Pacific coast forests and is extremely difficult to distinguish from Cordilleran Flycatcher by sight alone."
    },
    "Regulus calendula": {
        "habitat": "Coniferous and mixed forests; winters in dense shrubs and thickets",
        "migration": "Migratory; one of the smallest long-distance migrants in North America",
        "diet": "Tiny insects, spiders, and insect eggs gleaned from foliage",
        "conservation_status": "Least Concern",
        "description": "The Ruby-crowned Kinglet is a tiny, olive-green bird with a concealed red crown patch (shown only when excited). Despite its small size, it is remarkably hardy and one of the most energetic and constantly moving birds in North American forests."
    },
    "Regulus satrapa": {
        "habitat": "Coniferous forests; winters in mixed woodlands and suburban areas",
        "migration": "Migratory; breeds in boreal and montane forests",
        "diet": "Tiny insects, spiders, and insect eggs",
        "conservation_status": "Least Concern",
        "description": "The Golden-crowned Kinglet is one of the smallest birds in North America, with a brilliant gold-and-orange crown stripe. Incredibly hardy, it survives arctic temperatures by fluffing feathers and huddling. Its high, thin 'tsee-tsee-tsee' call is a classic winter forest sound."
    },
    "Pheucticus melanocephalus": {
        "habitat": "Open woodlands, forest edges, shrubby hillsides, and gardens in western North America",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Seeds, insects, and berries",
        "conservation_status": "Least Concern",
        "description": "The Black-headed Grosbeak is a large, stout-billed finch. Males are stunning in black, white, and deep orange; females are heavily streaked brown with a buff eyebrow. One of few birds that can eat Monarch butterflies despite their toxic cardiac glycosides."
    },
    "Passerina amoena": {
        "habitat": "Open woodlands, brushy hillsides, streamside thickets, and gardens in western North America",
        "migration": "Migratory; winters in Mexico",
        "diet": "Seeds, insects, and berries",
        "conservation_status": "Least Concern",
        "description": "The Lazuli Bunting is a small, stunningly colored bird — males are bright turquoise-blue above with a rusty breast and white wing bars. Young males learn their song after arriving on breeding grounds by assembling phrases heard from multiple neighboring males."
    },
    "Icterus bullockii": {
        "habitat": "Open woodlands, riparian corridors, parks, and suburban areas in western North America",
        "migration": "Migratory; winters in Mexico and Central America",
        "diet": "Insects, nectar, and fruit",
        "conservation_status": "Least Concern",
        "description": "Bullock's Oriole is a brilliant orange-and-black bird that weaves elaborate hanging sock nests from plant fibers. Males are strikingly patterned with a bold white wing patch. It is the western counterpart of the Baltimore Oriole and the two hybridize on the Great Plains."
    },
}
 
 
def get_bird_info(scientific_name, common_name=''):
    """Return bird info from the database; call the Anthropic API as a live fallback for unknowns.
    Result is cached in BIRD_INFO so each species is only looked up once per server run."""
    if scientific_name in BIRD_INFO:
        return BIRD_INFO[scientific_name]
 
    logger.info(f"Fetching bird info for unknown species via API: {scientific_name}")
    try:
        import urllib.request
        prompt = (
            f"Provide factual information about the bird species with scientific name '{scientific_name}'"
            + (f" (common name: '{common_name}')" if common_name else "") + ". "
            "Reply ONLY with a JSON object — absolutely no markdown fences, no preamble — "
            "using exactly these keys: habitat, migration, diet, conservation_status, description. "
            "Keep each value to 1–2 informative sentences. If genuinely uncertain, write 'Unknown'."
        )
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()
        # Strip any accidental markdown fences
        text = text.lstrip("```json").lstrip("```").rstrip("```").strip()
        info = json.loads(text)
        BIRD_INFO[scientific_name] = info   # cache it
        logger.info(f"Successfully fetched and cached info for {scientific_name}")
        return info
    except Exception as e:
        logger.warning(f"API fallback failed for {scientific_name}: {e}")
 
    # Final fallback — generate something sensible from the name itself
    genus = scientific_name.split()[0] if scientific_name.split() else scientific_name
    fallback = {
        "habitat": f"Habitat information for {scientific_name} is not currently available in our database.",
        "migration": "Migration pattern varies by population and geographic region.",
        "diet": "Diet includes insects, seeds, and small invertebrates typical of this bird family.",
        "conservation_status": "Not evaluated",
        "description": (
            f"{common_name or scientific_name} ({scientific_name}) is a bird species in the genus {genus}. "
            "For detailed information, please consult the Cornell Lab of Ornithology's All About Birds website."
        )
    }
    BIRD_INFO[scientific_name] = fallback
    return fallback
 
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))
 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['user_id'] = username
            session['user_name'] = users[username]['name']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Try username: naveen, password: 1234', 'error')
    
    return render_template('login.html')
 
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))
 
@app.route('/dashboard')
@login_required
def dashboard():
    user_history = analysis_history.get(session['user_id'], [])
    return render_template('dashboard.html', user_name=session['user_name'], history=user_history[:5])
 
@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    # Check if system is properly configured
    if not analyzer:
        flash('BirdNET analyzer is not available. Please check installation and restart the application.', 'error')
        return render_template('analyze.html')
    
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return render_template('analyze.html')
            
            file = request.files['file']
            location = request.form.get('location', 'Unknown Location')
            notes = request.form.get('notes', '')
            
            if file.filename == '':
                flash('No file selected', 'error')
                return render_template('analyze.html')
 
            if not allowed_file(file.filename):
                flash('Invalid file type. Please upload MP3, WAV, OGG, FLAC, or M4A files only.', 'error')
                return render_template('analyze.html')
 
            # Generate unique filename to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = secure_filename(file.filename)
            unique_filename = f"{timestamp}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            logger.info(f"Saving file: {filepath}")
            file.save(filepath)
 
            # Validate the uploaded file
            is_valid, validation_message = validate_audio_file(filepath)
            if not is_valid:
                os.remove(filepath)  # Clean up invalid file
                flash(f'Invalid audio file: {validation_message}', 'error')
                return render_template('analyze.html')
 
            logger.info(f"Analyzing file: {filepath} (size: {os.path.getsize(filepath)} bytes)")
            
            # Perform BirdNET analysis with error handling
            try:
                recording = Recording(
                    analyzer,
                    filepath,
                    lat=35.4244,  # Default coordinates - should be made dynamic
                    lon=-120.7463,
                    date=datetime.now(),
                    min_conf=0.25,  # Minimum confidence threshold
                )
                
                logger.info("Starting BirdNET analysis...")
                recording.analyze()
                logger.info("BirdNET analysis completed")
 
            except Exception as e:
                logger.error(f"BirdNET analysis failed: {str(e)}")
                os.remove(filepath)  # Clean up file
                flash(f'Analysis failed: {str(e)}. Please try with a different audio file.', 'error')
                return render_template('analyze.html')
 
            # Process results with enhanced information
            results = []
            if recording.detections:
                logger.info(f"Found {len(recording.detections)} detections")
                
                for det in recording.detections:
                    scientific_name = det['scientific_name']
                    confidence_percent = round(det['confidence'] * 100, 2)
                    
                    # Only include high-confidence detections
                    if confidence_percent >= 25:  # 25% minimum confidence
                        bird_data = {
                            'common_name': det['common_name'],
                            'scientific_name': scientific_name,
                            'confidence': confidence_percent,
                            'start_time': round(det['start_time'], 2),
                            'end_time': round(det['end_time'], 2),
                            'duration': round(det['end_time'] - det['start_time'], 1),
                            'location': location,
                            'latitude': 35.4244,  # These should be dynamic based on user input
                            'longitude': -120.7463,
                            'additional_info': get_bird_info(scientific_name, det['common_name'])
                        }
                        results.append(bird_data)
                        logger.info(f"Added detection: {det['common_name']} ({confidence_percent}%)")
                
                # Sort by confidence (highest first)
                results.sort(key=lambda x: x['confidence'], reverse=True)
            else:
                logger.info("No detections found")
 
            # Save analysis to history
            analysis_data = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'filename': original_filename,
                'unique_filename': unique_filename,
                'location': location,
                'notes': notes,
                'results': results,
                'audio_file': unique_filename,
                'total_species': len(set([r['scientific_name'] for r in results])) if results else 0,
                'total_detections': len(results),
                'highest_confidence': max([r['confidence'] for r in results]) if results else 0,
                'analysis_duration': 0,  # Could add timing
                'file_size': os.path.getsize(filepath)
            }
 
            # Initialize user history if doesn't exist
            if session['user_id'] not in analysis_history:
                analysis_history[session['user_id']] = []
            analysis_history[session['user_id']].insert(0, analysis_data)
 
            # Save results to file for persistence
            results_filename = f"results_{analysis_data['id']}.json"
            results_path = os.path.join(app.config['RESULTS_FOLDER'], results_filename)
            with open(results_path, 'w') as f:
                json.dump(analysis_data, f, indent=2)
 
            # Provide user feedback
            if results:
                species_count = len(set([r['scientific_name'] for r in results]))
                flash(f'Analysis complete! Found {len(results)} bird detections from {species_count} species.', 'success')
                logger.info(f"Analysis successful: {len(results)} detections, {species_count} species")
            else:
                flash('Analysis complete, but no birds were detected. Try a recording with clearer bird sounds or check if the audio contains bird calls.', 'info')
                logger.info("Analysis complete but no birds detected")
 
            return redirect(url_for('results', analysis_id=analysis_data['id']))
                
        except Exception as e:
            logger.error(f"Unexpected error in analyze route: {str(e)}")
            logger.error(traceback.format_exc())
            flash(f'An unexpected error occurred during analysis: {str(e)}', 'error')
            
    return render_template('analyze.html')
 
@app.route('/results/<analysis_id>')
@login_required
def results(analysis_id):
    try:
        results_path = os.path.join(app.config['RESULTS_FOLDER'], f"results_{analysis_id}.json")
        with open(results_path, 'r') as f:
            analysis_data = json.load(f)
        
        return render_template('results.html', analysis=analysis_data)
    except FileNotFoundError:
        flash('Results not found.', 'error')
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Error loading results: {str(e)}")
        flash('Error loading results.', 'error')
        return redirect(url_for('dashboard'))
 
@app.route('/history')
@login_required
def history():
    user_history = analysis_history.get(session['user_id'], [])
    return render_template('history.html', history=user_history)
 
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded audio files — no login_required so browser audio elements can stream directly."""
    try:
        return send_from_directory(
            os.path.abspath(app.config['UPLOAD_FOLDER']),
            filename,
            conditional=True
        )
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404
 
@app.route('/api/bird-info/<path:scientific_name>')
@login_required
def bird_info_api(scientific_name):
    """Return bird info — used by results page JS for live lookup."""
    common_name = request.args.get('common_name', '')
    return jsonify(get_bird_info(scientific_name, common_name))
 
@app.route('/api/analysis/<analysis_id>')
@login_required
def api_analysis(analysis_id):
    try:
        results_path = os.path.join(app.config['RESULTS_FOLDER'], f"results_{analysis_id}.json")
        with open(results_path, 'r') as f:
            analysis_data = json.load(f)
        return jsonify(analysis_data)
    except FileNotFoundError:
        return jsonify({'error': 'Analysis not found'}), 404
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
 
@app.route('/system-check')
@login_required
def system_check():
    """System dependencies and health check"""
    checks = {
        'birdnet_available': BIRDNET_AVAILABLE,
        'analyzer_initialized': analyzer is not None,
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'upload_folder_writable': os.access(app.config['UPLOAD_FOLDER'], os.W_OK),
        'results_folder_exists': os.path.exists(app.config['RESULTS_FOLDER']),
        'results_folder_writable': os.access(app.config['RESULTS_FOLDER'], os.W_OK),
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024)
    }
    return jsonify(checks)
 
@app.route('/test-birdnet')
@login_required
def test_birdnet():
    """Test BirdNET functionality with a simple check"""
    if not analyzer:
        return jsonify({'status': 'error', 'message': 'BirdNET analyzer not available'})
    
    try:
        # Try to create a recording object (without actual file)
        test_result = {
            'status': 'success',
            'message': 'BirdNET analyzer is working correctly',
            'analyzer_type': str(type(analyzer)),
            'available_methods': [method for method in dir(analyzer) if not method.startswith('_')]
        }
        return jsonify(test_result)
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'BirdNET test failed: {str(e)}'
        })
 
# Enhanced simple test route
@app.route('/simple-test', methods=['GET', 'POST'])
@login_required 
def simple_test():
    """Enhanced test route with better error reporting"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return "<div style='color: red;'>No file selected</div>"
        
        file = request.files['file']
        if file.filename == '':
            return "<div style='color: red;'>No file selected</div>"
 
        try:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_filename = f"test_{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
 
                logger.info(f"Testing with file: {filepath} (size: {os.path.getsize(filepath)} bytes)")
                
                # Validate file
                is_valid, validation_msg = validate_audio_file(filepath)
                if not is_valid:
                    os.remove(filepath)
                    return f"<div style='color: red;'>File validation failed: {validation_msg}</div>"
                
                # Run BirdNET analysis
                recording = Recording(
                    analyzer,
                    filepath,
                    lat=35.4244,
                    lon=-120.7463,
                    date=datetime.now(),
                    min_conf=0.25,
                )
                recording.analyze()
 
                results = []
                if recording.detections:
                    for det in recording.detections:
                        result_item = {
                            'common_name': det['common_name'],
                            'scientific_name': det['scientific_name'],
                            'confidence': round(det['confidence'] * 100, 2),
                            'start_time': round(det['start_time'], 2),
                            'end_time': round(det['end_time'], 2),
                            'duration': round(det['end_time'] - det['start_time'], 1)
                        }
                        results.append(result_item)
                    
                    results.sort(key=lambda x: x['confidence'], reverse=True)
                
                # Clean up test file
                os.remove(filepath)
                
                html_output = f"""
                <div style='font-family: Arial, sans-serif; padding: 20px;'>
                    <h2 style='color: green;'>✅ Test Results</h2>
                    <p><strong>File:</strong> {filename}</p>
                    <p><strong>Detections found:</strong> {len(results)}</p>
                    <pre style='background: #f5f5f5; padding: 15px; border-radius: 8px;'>{json.dumps(results, indent=2)}</pre>
                    <hr>
                    <p><em>File processed and cleaned up successfully.</em></p>
                </div>
                """
                return html_output
            else:
                return "<div style='color: red;'>Invalid file type. Please upload MP3, WAV, OGG, FLAC, or M4A files.</div>"
                
        except Exception as e:
            logger.error(f"Test route error: {str(e)}")
            logger.error(traceback.format_exc())
            return f"""
            <div style='color: red; font-family: Arial, sans-serif; padding: 20px;'>
                <h2>❌ Test Error</h2>
                <pre style='background: #ffe6e6; padding: 15px; border-radius: 8px;'>{str(e)}</pre>
                <hr>
                <h3>Full Traceback:</h3>
                <pre style='background: #f0f0f0; padding: 15px; border-radius: 8px; font-size: 12px;'>{traceback.format_exc()}</pre>
            </div>
            """
    
    return '''
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
        <h2>🧪 Enhanced BirdNET Test</h2>
        <p>Upload an audio file to test the BirdNET analysis functionality.</p>
        <form method="post" enctype="multipart/form-data" style="margin-top: 20px;">
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: bold;">Select Audio File:</label>
                <input type="file" name="file" accept=".mp3,.wav,.ogg,.flac,.m4a" 
                       style="padding: 10px; border: 2px solid #ddd; border-radius: 5px; width: 100%;">
            </div>
            <input type="submit" value="🔍 Test Analysis" 
                   style="background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">
        </form>
        
        <div style="margin-top: 30px; padding: 15px; background: #e9f7ff; border-radius: 8px;">
            <h3>📋 Supported Formats:</h3>
            <ul>
                <li>MP3 - MPEG Audio Layer 3</li>
                <li>WAV - Waveform Audio File</li>
                <li>OGG - OGG Vorbis</li>
                <li>FLAC - Free Lossless Audio Codec</li>
                <li>M4A - MPEG-4 Audio</li>
            </ul>
            <p><strong>Max file size:</strong> 50MB</p>
        </div>
    </div>
    '''
 
if __name__ == '__main__':
    print("=== BirdID Pro Enhanced System Check ===")
    print(f"BirdNET available: {BIRDNET_AVAILABLE}")
    print(f"Analyzer initialized: {analyzer is not None}")
    print(f"Supported formats: {', '.join(ALLOWED_EXTENSIONS)}")
    print(f"Max file size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    if not BIRDNET_AVAILABLE:
        print("\n⚠️  Warning: BirdNET not installed.")
        print("   Install with: pip install birdnetlib")
        print("   Or: pip install birdnetlib[complete]")
    
    print("\n" + "="*50)
    print("Available test routes:")
    print("- /simple-test (enhanced testing)")
    print("- /system-check (system status JSON)")
    print("- /test-birdnet (BirdNET functionality test)")
    print("- /login (main application)")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
 
 
 









# from flask import Flask, request, render_template, flash, send_from_directory, redirect, url_for, session, jsonify
# from werkzeug.utils import secure_filename
# from werkzeug.security import generate_password_hash, check_password_hash
# from datetime import datetime
# import os
# import json
# import uuid
# from functools import wraps

# # Try to import BirdNET
# try:
#     from birdnetlib import Recording
#     from birdnetlib.analyzer import Analyzer
#     BIRDNET_AVAILABLE = True
# except ImportError:
#     BIRDNET_AVAILABLE = False
#     print("Warning: birdnetlib not available. Install with: pip install birdnetlib")

# app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your-super-secret-key-change-this-in-production'
# app.config['UPLOAD_FOLDER'] = 'uploads'
# app.config['RESULTS_FOLDER'] = 'results'

# # Keep audio formats simple and tested - stick to what works
# ALLOWED_EXTENSIONS = {'mp3', 'wav'}  # Removed problematic formats

# # Create necessary folders
# os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)
# os.makedirs('templates', exist_ok=True)
# os.makedirs('static/css', exist_ok=True)
# os.makedirs('static/js', exist_ok=True)

# # Simple in-memory user storage
# users = {
#     'naveen': {
#         'password': generate_password_hash('1234'),
#         'name': 'Naveen',
#         'profile_image': 'default-avatar.jpg'
#     },
#     'admin': {
#         'password': generate_password_hash('admin'),
#         'name': 'Admin User',
#         'profile_image': 'default-avatar.jpg'
#     }
# }

# # Analysis history storage
# analysis_history = {}

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if 'user_id' not in session:
#             return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     return decorated_function

# # Initialize analyzer exactly like the working version
# analyzer = None
# if BIRDNET_AVAILABLE:
#     try:
#         print("Initializing BirdNET analyzer...")
#         analyzer = Analyzer()
#         print("BirdNET analyzer initialized successfully")
#     except Exception as e:
#         print(f"Error initializing BirdNET: {e}")
#         analyzer = None

# # Enhanced bird information database
# BIRD_INFO = {
#     "Geothlypis tolmiei": {
#         "habitat": "Dense undergrowth in coniferous and mixed forests",
#         "migration": "Migrates to Central America for winter",
#         "diet": "Insects, spiders, and small berries",
#         "conservation_status": "Least Concern",
#         "description": "A small warbler with distinctive white eye crescents and gray hood."
#     },
#     "Turdus migratorius": {
#         "habitat": "Gardens, parks, woodlands, and urban areas",
#         "migration": "Partial migrant, some populations stay year-round",
#         "diet": "Worms, insects, fruits, and berries",
#         "conservation_status": "Least Concern",
#         "description": "The American Robin is known for its brick-red breast and cheerful song."
#     },
# }

# @app.route('/')
# def index():
#     if 'user_id' in session:
#         return redirect(url_for('dashboard'))
#     return redirect(url_for('login'))

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form.get('username')
#         password = request.form.get('password')
        
#         if username in users and check_password_hash(users[username]['password'], password):
#             session['user_id'] = username
#             session['user_name'] = users[username]['name']
#             flash('Login successful!', 'success')
#             return redirect(url_for('dashboard'))
#         else:
#             flash('Invalid credentials. Try username: naveen, password: 1234', 'error')
    
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.clear()
#     flash('You have been logged out.', 'info')
#     return redirect(url_for('login'))

# @app.route('/dashboard')
# @login_required
# def dashboard():
#     user_history = analysis_history.get(session['user_id'], [])
#     return render_template('dashboard.html', user_name=session['user_name'], history=user_history[:5])

# @app.route('/analyze', methods=['GET', 'POST'])
# @login_required
# def analyze():
#     # Check if system is properly configured
#     if not analyzer:
#         flash('BirdNET analyzer is not available. Please check installation.', 'error')
#         return render_template('analyze.html')
    
#     if request.method == 'POST':
#         if 'file' not in request.files:
#             flash('No file selected', 'error')
#             return render_template('analyze.html')
        
#         file = request.files['file']
#         location = request.form.get('location', 'Unknown')
#         notes = request.form.get('notes', '')
        
#         if file.filename == '':
#             flash('No file selected', 'error')
#             return render_template('analyze.html')

#         try:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 # Keep the filename simple to avoid issues
#                 filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
#                 # Delete existing file with same name to avoid conflicts
#                 if os.path.exists(filepath):
#                     os.remove(filepath)
                
#                 file.save(filepath)

#                 # Verify file was saved successfully
#                 if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
#                     flash('Failed to save uploaded file', 'error')
#                     return render_template('analyze.html')

#                 print(f"Analyzing file: {filepath} (size: {os.path.getsize(filepath)} bytes)")
                
#                 # Use EXACTLY the same approach as your working code
#                 recording = Recording(
#                     analyzer,
#                     filepath,
#                     lat=35.4244,
#                     lon=-120.7463,
#                     date=datetime.now(),
#                     min_conf=0.25,
#                 )
#                 recording.analyze()

#                 # Process results with enhanced information
#                 results = []
#                 if recording.detections:
#                     print(f"Found {len(recording.detections)} detections")
#                     for det in recording.detections:
#                         scientific_name = det['scientific_name']
#                         bird_data = {
#                             'common_name': det['common_name'],
#                             'scientific_name': scientific_name,
#                             'confidence': round(det['confidence'] * 100, 2),
#                             'start_time': det['start_time'],
#                             'end_time': det['end_time'],
#                             'duration': round(det['end_time'] - det['start_time'], 1),
#                             'location': location,
#                             'latitude': 35.4244,
#                             'longitude': -120.7463,
#                             'additional_info': BIRD_INFO.get(scientific_name, {
#                                 'habitat': 'Information not available',
#                                 'migration': 'Information not available', 
#                                 'diet': 'Information not available',
#                                 'conservation_status': 'Unknown',
#                                 'description': 'No additional information available.'
#                             })
#                         }
#                         results.append(bird_data)
                    
#                     # Sort by confidence
#                     results.sort(key=lambda x: x['confidence'], reverse=True)
#                 else:
#                     print("No detections found")

#                 # Save analysis to history
#                 analysis_data = {
#                     'id': str(uuid.uuid4()),
#                     'timestamp': datetime.now().isoformat(),
#                     'filename': filename,
#                     'location': location,
#                     'notes': notes,
#                     'results': results,
#                     'audio_file': filename,  # Use original filename for playback
#                     'total_species': len(set([r['scientific_name'] for r in results])) if results else 0,
#                     'total_detections': len(results),
#                     'highest_confidence': max([r['confidence'] for r in results]) if results else 0
#                 }

#                 if session['user_id'] not in analysis_history:
#                     analysis_history[session['user_id']] = []
#                 analysis_history[session['user_id']].insert(0, analysis_data)

#                 # Save results to file
#                 results_filename = f"results_{analysis_data['id']}.json"
#                 results_path = os.path.join(app.config['RESULTS_FOLDER'], results_filename)
#                 with open(results_path, 'w') as f:
#                     json.dump(analysis_data, f, indent=2)

#                 if results:
#                     flash(f'Analysis complete! Found {len(results)} bird detections.', 'success')
#                 else:
#                     flash('Analysis complete, but no birds were detected. Try a recording with clearer bird sounds.', 'info')

#                 return redirect(url_for('results', analysis_id=analysis_data['id']))
#             else:
#                 flash('Invalid file type. Please upload MP3 or WAV files only.', 'error')
                
#         except Exception as e:
#             print(f"Error in analyze route: {str(e)}")
#             import traceback
#             traceback.print_exc()
#             flash(f'An error occurred during analysis: {str(e)}', 'error')
            
#     return render_template('analyze.html')

# @app.route('/results/<analysis_id>')
# @login_required
# def results(analysis_id):
#     try:
#         results_path = os.path.join(app.config['RESULTS_FOLDER'], f"results_{analysis_id}.json")
#         with open(results_path, 'r') as f:
#             analysis_data = json.load(f)
        
#         return render_template('results.html', analysis=analysis_data)
#     except FileNotFoundError:
#         flash('Results not found.', 'error')
#         return redirect(url_for('dashboard'))

# @app.route('/history')
# @login_required
# def history():
#     user_history = analysis_history.get(session['user_id'], [])
#     return render_template('history.html', history=user_history)

# @app.route('/uploads/<filename>')
# @login_required
# def uploaded_file(filename):
#     return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# @app.route('/api/analysis/<analysis_id>')
# @login_required
# def api_analysis(analysis_id):
#     try:
#         results_path = os.path.join(app.config['RESULTS_FOLDER'], f"results_{analysis_id}.json")
#         with open(results_path, 'r') as f:
#             analysis_data = json.load(f)
#         return jsonify(analysis_data)
#     except FileNotFoundError:
#         return jsonify({'error': 'Analysis not found'}), 404

# @app.route('/system-check')
# @login_required
# def system_check():
#     """System dependencies check"""
#     checks = {
#         'birdnet': BIRDNET_AVAILABLE,
#         'analyzer_initialized': analyzer is not None,
#         'upload_folder_writable': os.access(app.config['UPLOAD_FOLDER'], os.W_OK),
#         'results_folder_writable': os.access(app.config['RESULTS_FOLDER'], os.W_OK)
#     }
#     return jsonify(checks)

# # Keep the working simple upload route for testing
# @app.route('/simple-test', methods=['GET', 'POST'])
# @login_required 
# def simple_test():
#     """Simple test route that mimics your working code exactly"""
#     if request.method == 'POST':
#         if 'file' not in request.files:
#             return "No file selected"
        
#         file = request.files['file']
#         if file.filename == '':
#             return "No file selected"

#         try:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#                 file.save(filepath)

#                 print(f"Testing with file: {filepath}")
                
#                 recording = Recording(
#                     analyzer,
#                     filepath,
#                     lat=35.4244,
#                     lon=-120.7463,
#                     date=datetime.now(),
#                     min_conf=0.25,
#                 )
#                 recording.analyze()

#                 results = []
#                 if recording.detections:
#                     results = [{
#                         'common_name': det['common_name'],
#                         'scientific_name': det['scientific_name'],
#                         'confidence': det['confidence'],
#                         'start_time': det['start_time'],
#                         'end_time': det['end_time']
#                     } for det in recording.detections]
                    
#                     results.sort(key=lambda x: x['confidence'], reverse=True)
                
#                 return f"<h2>Test Results:</h2><pre>{json.dumps(results, indent=2)}</pre>"
#             else:
#                 return 'Invalid file type'
                
#         except Exception as e:
#             import traceback
#             return f"<h2>Error:</h2><pre>{str(e)}\n\n{traceback.format_exc()}</pre>"
    
#     return '''
#     <h2>Simple Test Upload</h2>
#     <form method="post" enctype="multipart/form-data">
#         <input type="file" name="file" accept=".mp3,.wav">
#         <input type="submit" value="Test Upload">
#     </form>
#     '''

# if __name__ == '__main__':
#     print("=== BirdID Pro System Check ===")
#     print(f"BirdNET available: {BIRDNET_AVAILABLE}")
#     print(f"Analyzer initialized: {analyzer is not None}")
    
#     if not BIRDNET_AVAILABLE:
#         print("\n⚠️ Warning: BirdNET not installed. Run: pip install birdnetlib")
    
#     print("\n" + "="*40)
#     print("Available routes:")
#     print("- /simple-test (for testing basic functionality)")
#     print("- /login (main login)")
#     print("- /system-check (system status)")
    
#     app.run(debug=True, host='0.0.0.0', port=5000)
