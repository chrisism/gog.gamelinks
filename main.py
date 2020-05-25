import sqlite3

db_path = '/home/cwjungerius/projects/assets/galaxy-2.0.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

#	Achievements
#	AvailableLanguages
#	AvailablePlugins
#	BaseModificationTargets
#	Builds
#	CloudSavesConfiguration
#	CloudSavesLocations
#	CloudSynchronisations
#	Dependencies
#	DependencyDirectories
#	DependencyFileChunkHashes
#	DependencyFiles
#	Details
#	Directories
#	DiskSizes
#	ExecutableSupportFileChunkHashes
#	ExecutableSupportFiles
#	ExternalAccounts
#	ExternalGameCompatibilities
#	FriendsRecentPlaySessions
#	GameFileChunkHashes
#   GameFiles
#   GameLinks
#   GamePieceCacheUpdateDates
#   GamePieceTypes
#   GamePieces
#   GameTimes
#   ImportedLatestBuildIds
#   InstalledBaseProducts
#   InstalledExternalProducts
#   InstalledProducts
#   Languages
#   LibraryReleases
#   LicensedReleases
#	LimitedDetails
#	LocalizedAchievements
#	Manifests
#	ModificationTargets
#	OsCompatibilities
#	OverlayConfiguration
#	PendingGameSessions
#	PlatformConnections
#	Platforms
#	PlayTaskLaunchParameters
#	PlayTaskTypes
#	PlayTasks
#	Plugins
#	Product Details View
#	ProductAuthorizations
#	ProductConfiguration
#	ProductDependencies
#	ProductDetailsResponse
#	ProductPurchaseDates
#	ProductSettings
#	ProductStates
#	Products
#	ProductsToReleaseKeys
#	QueryPieceParameterNames
#	QueryPieceParameters
#	QueryPieceTypes
#	QueryPieces
#	ReleaseKeys
#	ReleaseProperties
#	SubscriptionReleases
#	Subscriptions
#	SupportDirectories
#	SupportFileChunkHashes
#	SupportFiles
#	SymbolicLinks
#	UserAchievements
#	UserPlugins
#	UserReleaseProperties
#	UserReleaseTags
#	Users
#	WebCache
#	WebCacheResourceTypes
#	WebCacheResources

#id	type
#1	1	myRating
#2	3	myAchievementsCount
#3	5	allGameReleases
#4	6	dlcs
#5	7	media
#6	8	originalImages
#7	9	originalMeta
#8	10	originalTitle
#9	11	osCompatibility
#10	12	meta
#11	13	summary
#12	14	title
#13	1861	changelog
#14	1862	goodies
#15	1863	isPreorder
#16	1864	productLinks
#17	1981	friendsOwning
#18	1982	myFriendsActivity
#19	2231	originalSortingTitle
#20	2242	sortingTitle

#	releaseKey	gamePieceTypeId	userId	value
#1	gog_1146738698	1	50788186949939540	{"myRating":null}
#2	gog_1434021265	1	50788186949939540	{"myRating":null}
#3	gog_1146738698	3	50788186949939540	{"all":0,"unlocked":0}

#releaseKey	userId	gameId
#1	gog_1146738698	50788186949939540	
#2	gog_1434021265	50788186949939540	
#3	gog_1180040534	50788186949939540	
#4	gog_1207665713	50788186949939540	

q = 'SELECT g.releaseKey, gpt.value, gpm.value \
    FROM GameLinks AS g \
        LEFT JOIN GamePieces AS gpt ON g.releaseKey = gpt.releaseKey AND gpt.gamePieceTypeId = 14 \
        LEFT JOIN GamePieces AS gpm ON g.releaseKey = gpm.releaseKey AND gpm.gamePieceTypeId = 12'

for row in c.execute(q):
    print(row)