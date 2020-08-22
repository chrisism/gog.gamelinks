 SELECT u.userId, u.isHidden,
            r.* 
            ,p.id AS platformId 
            ,IFNULL(p.name, "gog") AS platform 
            ,gpt.value as title 
            ,gps.value as summary 
            ,gpm.value as meta 
            ,gpmd.value as media 
            ,gpi.value as images 
            ,gpo.value AS sort 
            ,CASE 
                WHEN prk.externalId IS NULL AND ig.productId IS NULL THEN 0 
                WHEN prk.externalId IS NOT NULL AND ie.id IS NULL THEN 0 
                ELSE 1 
            END AS Installed 
        FROM UserReleaseProperties AS u
            LEFT JOIN ReleaseProperties AS r ON u.releaseKey = r.releaseKey
            LEFT JOIN ProductsToReleaseKeys AS prk ON r.releaseKey = prk.releaseKey 
            LEFT JOIN Platforms AS p ON INSTR(r.releaseKey, p.name) > 0 
            LEFT JOIN GamePieces AS gpt ON r.releaseKey = gpt.releaseKey 
                INNER JOIN GamePieceTypes gtypes1 ON gpt.gamePieceTypeId = gtypes1.Id AND gtypes1.type = 'title' 
            LEFT JOIN GamePieces AS gps ON r.releaseKey = gps.releaseKey 
                INNER JOIN GamePieceTypes gtypes2 ON gps.gamePieceTypeId = gtypes2.Id AND gtypes2.type = 'summary' 
            LEFT JOIN GamePieces AS gpm  ON r.releaseKey = gpm.releaseKey 
                INNER JOIN GamePieceTypes gtypes3 ON gpm.gamePieceTypeId = gtypes3.Id AND gtypes3.type = 'meta' 
            LEFT JOIN GamePieces AS gpmd ON r.releaseKey = gpmd.releaseKey 
                INNER JOIN GamePieceTypes gtypes4 ON gpmd.gamePieceTypeId = gtypes4.Id AND gtypes4.type = 'media' 
            LEFT JOIN GamePieces AS gpi  ON r.releaseKey = gpi.releaseKey 
                INNER JOIN GamePieceTypes gtypes5 ON gpi.gamePieceTypeId = gtypes5.Id AND gtypes5.type = 'originalImages' 
            LEFT JOIN GamePieces AS gpo  ON r.releaseKey = gpo.releaseKey 
                INNER JOIN GamePieceTypes gtypes6 ON gpo.gamePieceTypeId = gtypes6.Id AND gtypes6.type = 'sortingTitle' 
            LEFT JOIN InstalledBaseProducts AS ig ON ig.productId = prk.gogId 
            LEFT JOIN InstalledExternalProducts AS ie ON ie.id = prk.externalId 
        WHERE isVisibleInLibrary = 1 AND isDlc = 0 AND u.isHidden = 0