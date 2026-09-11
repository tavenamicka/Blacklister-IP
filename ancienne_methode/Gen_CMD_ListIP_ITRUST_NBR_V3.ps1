# coller après enable et conf t 

#Définition et placement dans le repertoire de travail Script PowerShell
$Path = "R:\DML\RESEAU\Guides_et_Procedures\Blocage_ip_Cisco_ASA_Palo\Blocage_ip_Cisco_ASA"

CD $Path

# Définir le nom du groupe
$Group_Name = "IOC-case_iTrust"

# Définir le préfixe de l'objet et initialiser son nom
$Object_Prefix = "ioc-case-iTrust-"
$Object_Name = @()

# Initialiser la liste des noms d'objet de réseau
$ListObjectName = @()

# Initialiser la liste des Adresses IP et des FQDNs
$ListIPAddress = @()

# Initialiser la liste des Adresses IP et FQDNs en double
$Duplicate = @()

# Initialiser la liste des Adresses IP et FQDNs invalides
$Invalid_Address = @()

# Initialiser la liste des commandes
$Commands = @()

#Définir la valeur Regex de contrôle IPV4
$RegexIPV4 = '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'

# Ajout de l'assembly pour l'explorer Windows
Add-Type -AssemblyName System.Windows.Forms

# Requeter le chemin d'accès du fichier contenant les Adresses IP
$IP_List_File_src = New-Object System.Windows.Forms.OpenFileDialog -Property @{ InitialDirectory = $Path }
$null = $IP_List_File_src.ShowDialog()

# Pour chaque Adresse IP dans le fichier
foreach ($IP in Get-Content  $IP_List_File_src.FileName) 
{
    # Vérifier si l'Adresse IP est valide
    if ("$IP" -match $RegexIPV4) 
	{
        # Vérifier si l'Adresse IP n'est pas déjà présente dans la liste
        if ($ListIPAddress -notcontains $IP) 
        {
            # Ajouter l'Adresse IP à la liste des Adresses IP
            $ListIPAddress += $IP
            
			# Créer le nom de l'objet de réseau
            $Object_Name = $Object_Prefix + $IP 
			
			# Ajouter l'objet de réseau à la liste des noms d'objet de réseau
            $ListObjectName += $Object_Name

            # Générer les commandes de configuration pour l'objet de réseau
            $Commands += Write-Output "object network $Object_Name"
            $Commands += Write-Output " host $IP"
            $Commands += Write-Output " description $Object_Name"
            $Commands += Write-Output "exit`n"
        }
        else 
        {
			# L'Adresse IP est en double
            $Duplicate += $IP
        }
	}
    else 
	{
        # Vérifier si la valeur est un FQDN valide
        <#if ([System.Net.Dns]::GetHostEntry("$IP")) 
		{
            # Vérifier si le FQDN n'est pas déjà présent dans la liste
            if ($ListIPAddress -notcontains $IP) 
            {
                # Ajouter le FQDN à la liste des Adresses IP
                $ListIPAddress += $IP

                # Créer le nom de l'objet de réseau
                $Object_Name = $Object_Prefix + $IP

                # Ajouter l'objet de réseau à la liste des noms d'objet de réseau
                $ListObjectName += $Object_Name

                # Générer les commandes de configuration pour l'objet de réseau
                $Commands += Write-Output "object network $Object_Name"
                $Commands += Write-Output " fqdn $IP"
                $Commands += Write-Output " description $Object_Name"
                $Commands += Write-Output "exit`n"
            }
            else 
			{
                # Le FQDN est en double
                $Duplicate += $IP
        }
			} #>
		# Adresse qui ne passe ni la validation IP ni celle FQDN
		$Invalid_Address += $IP
    }
}


# Générer les commandes de configuration pour le groupe d'objets de réseau
$Commands += Write-Output "object-group network $Group_Name"
foreach ($Object in $ListObjectName) 
{
    $Commands += Write-Output " network-object object $Object"
}
$Commands += Write-Output "exit`n"

# Écrire les commandes de configuration dans un fichier texte
$output_file = "$Path\Commandes_IOC-case_iTrust.txt"
$Commands | Out-File $output_file -Encoding utf8

# Écrire les Adresses IP et FQDN en doublon dans un fichier texte
$Duplicate_Address_file = "$Path\Duplicate_Address_IOC-case_iTrust.txt"
$Duplicate | Out-File $Duplicate_Address_file -Encoding utf8

# Écrire les Adresses qui ne passent ni la validation IP ni celle FQDN
$Invalid_Address_file = "$Path\Invalid_Address_IOC-case_iTrust.txt"
$Invalid_Address | Out-File $Invalid_Address_file -Encoding utf8

Write-Output "Les Adresses IP et FQDN en double: "
Write-Output $Duplicate`n
Write-Output "Les Adresses Invalides: "
Write-Output $Invalid_Address`n

# Afficher un message pour indiquer que le traitement est terminé
Write-Output "Le traitement est fini. 
Les commandes de configuration 		-> $output_file. 
Les Adresses IP et FQDN en double 	-> $Duplicate_Address_file. 
Les Adresses IP et FQDN invalides	-> $Invalid_Address_file.`n"

pause



